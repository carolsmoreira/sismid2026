"""Evaluate Rio dengue nowcasts against 2025 SINAN notifications.

Inputs are the archived weekly CSVs in this folder.  The script writes the fixed
and dynamic multiple-linear-regression predictions, metrics, and comparison plot.
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
TREND_FEATURES = ["dengue", "fever", "sintomas_de_dengue"]
FEATURES = [*TREND_FEATURES, "dengue_pt_wikipedia"]


def metrics(actual, predicted):
    return {
        "mae": mean_absolute_error(actual, predicted),
        "rmse": mean_squared_error(actual, predicted) ** 0.5,
        "pearson_r": actual.corr(predicted),
        "predicted_total": predicted.sum(),
    }


def add_wikipedia_pageviews(data: pd.DataFrame) -> pd.DataFrame:
    """Join monthly Portuguese Wikipedia dengue pageviews to weekly data."""
    wiki = pd.read_csv(
        HERE.parent / "wikipedia" / "dengue_pageviews_en_es_pt.csv",
        parse_dates=["date"],
    )[["date", "dengue_pt"]].rename(columns={"dengue_pt": "dengue_pt_wikipedia"})
    result = pd.merge_asof(
        data.sort_values("date"), wiki.sort_values("date"), on="date", direction="backward"
    )
    if result[FEATURES].isna().any().any():
        raise ValueError("Missing Google Trends or Wikipedia predictor values")
    return result


def main():
    trends = pd.read_csv(HERE / "my_topic_search.csv", parse_dates=["date"])
    train = pd.read_csv(
        HERE / "rio_dengue_trends_vs_sinan_2024_weekly.csv", parse_dates=["date"]
    )[["date", *TREND_FEATURES, "sinan_notified_cases"]]
    actual_2025 = pd.read_csv(
        HERE / "rio_dengue_sinan_2025_weekly.csv", parse_dates=["date"]
    )
    # The final 2024 row overlaps the first 2025 outcome week, where its archived
    # 2024 extract recorded zero notifications. Retain the 2025 value only.
    train = train.query("date <= '2024-12-22'")
    test = trends[
        (trends["date"] >= "2024-12-29") & (trends["date"] <= "2025-12-21")
    ][["date", *TREND_FEATURES]].merge(actual_2025, on="date", how="left")
    test["sinan_notified_cases"] = test["sinan_notified_cases"].fillna(0).astype(int)
    train = add_wikipedia_pageviews(train)
    test = add_wikipedia_pageviews(test)

    # Fixed model: all coefficients are estimated from 2024 only.
    fixed = make_pipeline(StandardScaler(), LinearRegression())
    fixed.fit(train[FEATURES], np.log1p(train["sinan_notified_cases"]))
    test["fixed_mlr_prediction"] = np.clip(
        np.expm1(fixed.predict(test[FEATURES])), 0, None
    )

    # Dynamic model: for each week, use only the preceding 52 observed weeks.
    observed = pd.concat([train, test], ignore_index=True).sort_values("date")
    dynamic_predictions = []
    for date in test["date"]:
        history = observed[observed["date"] < date].tail(52)
        model = make_pipeline(StandardScaler(), LinearRegression())
        model.fit(history[FEATURES], np.log1p(history["sinan_notified_cases"]))
        row = test.loc[test["date"].eq(date), FEATURES]
        dynamic_predictions.append(max(0, float(np.expm1(model.predict(row)[0]))))
    test["dynamic_52_week_prediction"] = dynamic_predictions

    actual = test["sinan_notified_cases"]
    results = pd.DataFrame(
        [
            {"model": "Fixed 2024 MLR", **metrics(actual, test["fixed_mlr_prediction"])},
            {
                "model": "Dynamic 52-week MLR",
                **metrics(actual, test["dynamic_52_week_prediction"]),
            },
        ]
    )
    test.to_csv(HERE / "rio_dengue_2025_mlr_dynamic_predictions.csv", index=False)
    results.to_csv(HERE / "rio_dengue_2025_mlr_dynamic_metrics.csv", index=False)

    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(test["date"], actual, color="#b22222", lw=2.8, label="SINAN notified cases")
    ax.plot(test["date"], test["fixed_mlr_prediction"], color="#1f77b4", lw=2.2,
            label="Fixed 2024 multiple linear regression")
    ax.plot(test["date"], test["dynamic_52_week_prediction"], color="#2ca02c", lw=2.2,
            label="Dynamic 52-week multiple linear regression")
    ax.set(title="Rio dengue nowcast, 2025: Google Trends + Wikipedia",
           xlabel="Week beginning", ylabel="Notified dengue cases")
    ax.grid(alpha=0.25)
    ax.legend(frameon=False)
    fig.text(
        0.5, 0.01,
        "Predictors: same-week Google Trends for dengue, fever, and sintomas de dengue; "
        "monthly Portuguese Wikipedia dengue pageviews.",
        ha="center", fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(HERE / "rio_dengue_2025_mlr_dynamic.png", dpi=180)

    print(results.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
