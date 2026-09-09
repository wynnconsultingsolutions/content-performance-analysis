"""
03_regression.py — Regression modeling of content performance.

Two OLS models:

  Model 1  log(audience_volume)   ~ content attributes   (reach / engagement)
  Model 2  log(worldwide_revenue) ~ content attributes   (commercial outcome)

Both use log outcomes because the raw distributions are heavily right-skewed;
coefficients are therefore read as approximate percentage effects.

Diagnostics reported: R-squared, adjusted R-squared, F-test, variance inflation
factors, and a residual plot.

Run:  python src/03_regression.py
"""

import sqlite3
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from statsmodels.stats.outliers_influence import variance_inflation_factor

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "content.db"
OUT = ROOT / "output"

# Reference levels for the categorical predictors. Every categorical
# coefficient is read as a difference from these.
REF_GENRE = "Drama"
REF_RATING = "R"
REF_ERA = "1990s"


def load(conn) -> pd.DataFrame:
    df = pd.read_sql_query("""
        SELECT genre, content_rating, creative_type, release_era,
               log_budget, log_audience_volume, log_worldwide_revenue,
               critic_score, audience_score, return_multiple,
               production_budget, worldwide_revenue, audience_volume
        FROM content
        WHERE genre          <> 'Unknown'
          AND content_rating <> 'Unknown'
          AND creative_type  <> 'Unknown'
          AND release_era    <> 'nan'
          AND log_budget           IS NOT NULL
          AND critic_score         IS NOT NULL
    """, conn)

    # Keep only genres with enough observations to estimate a coefficient.
    keep = df["genre"].value_counts()
    df = df[df["genre"].isin(keep[keep >= 25].index)]

    # Set reference levels explicitly so the output is readable.
    for col, ref in [("genre", REF_GENRE), ("content_rating", REF_RATING),
                     ("release_era", REF_ERA)]:
        levels = [ref] + [v for v in sorted(df[col].unique()) if v != ref]
        df[col] = pd.Categorical(df[col], categories=levels)

    return df


def fit(df: pd.DataFrame, outcome: str) -> sm.regression.linear_model.RegressionResults:
    data = df.dropna(subset=[outcome, "log_budget", "critic_score"])
    formula = (
        f"{outcome} ~ log_budget + critic_score + C(genre) + "
        "C(content_rating) + C(creative_type) + C(release_era)"
    )
    return smf.ols(formula, data=data).fit()


def vif_table(df: pd.DataFrame, outcome: str) -> pd.DataFrame:
    """Variance inflation factors for the continuous predictors."""
    data = df.dropna(subset=[outcome, "log_budget", "critic_score"])
    X = sm.add_constant(data[["log_budget", "critic_score"]])
    return pd.DataFrame({
        "predictor": X.columns,
        "vif": [variance_inflation_factor(X.values, i) for i in range(X.shape[1])],
    })


def tidy(res, top: int = 14) -> pd.DataFrame:
    """Coefficient table, significant terms first, with % effect for logs."""
    out = pd.DataFrame({
        "term": res.params.index,
        "coef": res.params.values,
        "std_err": res.bse.values,
        "p_value": res.pvalues.values,
    })
    out = out[out["term"] != "Intercept"].copy()
    # For a log outcome, exp(coef) - 1 is the approximate proportional effect.
    out["pct_effect"] = (np.exp(out["coef"]) - 1) * 100
    out["sig"] = np.where(out["p_value"] < 0.01, "***",
                 np.where(out["p_value"] < 0.05, "**",
                 np.where(out["p_value"] < 0.10, "*", "")))
    out["term"] = (out["term"]
                   .str.replace(r"C\((\w+)\)\[T\.", r"\1: ", regex=True)
                   .str.replace("]", "", regex=False))
    return out.reindex(out["coef"].abs().sort_values(ascending=False).index).head(top)


def residual_plot(res, title: str, fname: str) -> None:
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(8.5, 3.4))
    a1.scatter(res.fittedvalues, res.resid, s=6, alpha=0.25, color="#2B6CB0")
    a1.axhline(0, color="#E53E3E", lw=1)
    a1.set_xlabel("Fitted value")
    a1.set_ylabel("Residual")
    a1.set_title("Residuals vs fitted", fontweight="bold", loc="left")

    sm.qqplot(res.resid, line="45", fit=True, ax=a2,
              markersize=3, alpha=0.3, color="#2B6CB0")
    a2.set_title("Normal Q-Q", fontweight="bold", loc="left")

    for ax in (a1, a2):
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(alpha=0.25)

    fig.suptitle(title, fontweight="bold", x=0.02, ha="left")
    fig.tight_layout()
    fig.savefig(OUT / fname, dpi=130)
    plt.close(fig)


def report(res, df, outcome: str, label: str, fname: str) -> None:
    print("\n" + "=" * 68)
    print(f"MODEL: {label}")
    print("=" * 68)
    print(f"Observations       {int(res.nobs):,}")
    print(f"R-squared          {res.rsquared:.3f}")
    print(f"Adj. R-squared     {res.rsquared_adj:.3f}")
    print(f"F-statistic        {res.fvalue:.1f}  (p = {res.f_pvalue:.2e})")
    print(f"\nReference levels: genre={REF_GENRE}, rating={REF_RATING}, "
          f"era={REF_ERA}")

    print("\nLargest effects (sig: *** p<.01, ** p<.05, * p<.10)")
    t = tidy(res)
    print(t[["term", "coef", "std_err", "p_value", "pct_effect", "sig"]]
          .to_string(index=False,
                     formatters={"coef": "{:.3f}".format,
                                 "std_err": "{:.3f}".format,
                                 "p_value": "{:.4f}".format,
                                 "pct_effect": "{:+.1f}%".format}))

    print("\nVariance inflation factors (continuous predictors)")
    print(vif_table(df, outcome).to_string(index=False,
                                           formatters={"vif": "{:.2f}".format}))

    residual_plot(res, f"Diagnostics — {label}", fname)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    with sqlite3.connect(DB) as conn:
        df = load(conn)
    print(f"Modeling sample: {len(df):,} titles across "
          f"{df['genre'].nunique()} genres")

    m1 = fit(df, "log_audience_volume")
    report(m1, df, "log_audience_volume",
           "Audience reach — log(audience volume)", "diagnostics_reach.png")

    m2 = fit(df, "log_worldwide_revenue")
    report(m2, df, "log_worldwide_revenue",
           "Commercial performance — log(worldwide revenue)",
           "diagnostics_revenue.png")

    with open(OUT / "model_summaries.txt", "w") as f:
        f.write("MODEL 1 — log(audience volume)\n")
        f.write(str(m1.summary()))
        f.write("\n\n\nMODEL 2 — log(worldwide revenue)\n")
        f.write(str(m2.summary()))
    print(f"\nFull summaries written to output/model_summaries.txt")


if __name__ == "__main__":
    main()
