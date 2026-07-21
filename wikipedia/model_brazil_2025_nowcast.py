"""Evaluate Brazil dengue nowcasts using Google Trends and Portuguese Wikipedia.

The fixed model is trained only on 2024 observations.  The dynamic model
refits each week using the preceding 52 observed weeks, so it incorporates
prior 2025 notifications as they become available.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


HERE = Path(__file__).resolve().parent
FEATURES = ["google_trends_dengue", "dengue_pt"]


def metrics(actual: pd.Series, predicted: pd.Series) -> dict[str, float]:
    return {
        "mae": mean_absolute_error(actual, predicted),
        "rmse": mean_squared_error(actual, predicted) ** 0.5,
        "pearson_r": actual.corr(predicted),
        "predicted_total": predicted.sum(),
    }


def assemble(year: int) -> pd.DataFrame:
    cases = pd.read_csv(HERE / f"brazil_sinan_dengue_{year}_weekly.csv", parse_dates=["date"])
    trends = pd.read_csv(
        HERE / f"brazil_google_trends_dengue_{year}_weekly.csv", parse_dates=["date"]
    ).rename(columns={"dengue": "google_trends_dengue"})
    wiki = pd.read_csv(HERE / "brazil_wikipedia_pt_2023_2025_monthly.csv", parse_dates=["date"])
    data = cases.merge(trends, on="date", how="left").sort_values("date")
    data = pd.merge_asof(data, wiki.sort_values("date"), on="date", direction="backward")
    if data[["sinan_notified_cases", *FEATURES]].isna().any().any():
        raise ValueError(f"Incomplete data after merging {year} sources")
    return data


def main() -> None:
    train = assemble(2024)
    # The final Sunday-starting week runs into January 2026, but the 2025
    # extract can contain only its first four days.  Do not score that partial
    # outcome as a full week.
    test = assemble(2025).query("date <= '2025-12-21'").copy()

    # Fixed model: coefficients are estimated using 2024 only.
    fixed = make_pipeline(StandardScaler(), LinearRegression())
    fixed.fit(train[FEATURES], np.log1p(train["sinan_notified_cases"]))
    test["fixed_2024_mlr_prediction"] = np.clip(
        np.expm1(fixed.predict(test[FEATURES])), 0, None
    )

    # Dynamic model: each prediction sees only notifications from earlier weeks.
    observed = pd.concat([train, test], ignore_index=True).sort_values("date")
    predictions = []
    for date in test["date"]:
        history = observed[observed["date"] < date].tail(52)
        model = make_pipeline(StandardScaler(), LinearRegression())
        model.fit(history[FEATURES], np.log1p(history["sinan_notified_cases"]))
        features = test.loc[test["date"].eq(date), FEATURES]
        predictions.append(max(0, float(np.expm1(model.predict(features)[0]))))
    test["dynamic_52_week_mlr_prediction"] = predictions

    actual = test["sinan_notified_cases"]
    results = pd.DataFrame([
        {"model": "Fixed 2024 MLR", **metrics(actual, test["fixed_2024_mlr_prediction"])},
        {"model": "Dynamic 52-week MLR", **metrics(actual, test["dynamic_52_week_mlr_prediction"])},
    ])
    test.to_csv(HERE / "brazil_dengue_2025_mlr_predictions.csv", index=False)
    results.to_csv(HERE / "brazil_dengue_2025_mlr_metrics.csv", index=False)

    fig, ax = plt.subplots(figsize=(12, 5.5))
    ax.plot(test["date"], actual, color="#b22222", lw=2.8, label="SINAN notifications")
    ax.plot(test["date"], test["fixed_2024_mlr_prediction"], color="#1f77b4", lw=2.2,
            label="Fixed 2024 MLR")
    ax.plot(test["date"], test["dynamic_52_week_mlr_prediction"], color="#2ca02c", lw=2.2,
            label="Dynamic 52-week MLR")
    ax.set(title="Brazil dengue nowcast, 2025: Google Trends + Wikipedia",
           xlabel="Week beginning", ylabel="SINAN notifications")
    ax.grid(alpha=0.25)
    ax.legend(frameon=False)
    fig.text(0.5, 0.01,
             "Fixed model: fit on 2024 only. Dynamic model: refit on the preceding 52 observed weeks.\n"
             "Predictors: same-week Brazil Google Trends interest and monthly Portuguese Wikipedia pageviews.",
             ha="center", fontsize=9)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(HERE / "brazil_dengue_2025_mlr_predictions.png", dpi=180)
    print(results.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
