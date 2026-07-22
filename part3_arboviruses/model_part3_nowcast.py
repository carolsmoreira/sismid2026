"""Evaluate disease-specific Portuguese attention signals against SINAN notifications."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import RidgeCV
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


HERE = Path(__file__).resolve().parent
OUTCOME = "sinan_notifications"
NUMERIC = ["google_trends", "wikipedia_pageviews"]


def scores(actual: pd.Series, predicted: pd.Series) -> dict[str, float]:
    return {
        "mae": mean_absolute_error(actual, predicted),
        "rmse": mean_squared_error(actual, predicted) ** 0.5,
        "pearson_r": actual.corr(predicted),
        "observed_total": actual.sum(),
        "predicted_total": predicted.sum(),
    }


def main() -> None:
    data = pd.read_csv(
        HERE / "brazil_arbovirus_notification_attention_2024_2025_weekly.csv",
        parse_dates=["date"],
    )
    # Surveillance-year extracts include the Sunday-starting boundary week from
    # the prior calendar year. Define 2024/25 by the archived weekly windows,
    # and omit the final partial week that crosses into 2026.
    train = data.query("date >= '2023-12-31' and date <= '2024-12-22'").copy()
    test = data.query("date >= '2024-12-29' and date <= '2025-12-21'").copy()
    analysis_data = pd.concat([train.assign(analysis_year=2024), test.assign(analysis_year=2025)])

    def add_seasonal_features(frame: pd.DataFrame) -> pd.DataFrame:
        """Add cyclic week-of-year terms, allowing each disease its own curve."""
        result = frame.copy()
        phase = 2 * np.pi * result["date"].dt.isocalendar().week.astype(float) / 52.18
        result["season_sin"] = np.sin(phase)
        result["season_cos"] = np.cos(phase)
        for disease in ("dengue", "chikungunya", "zika"):
            indicator = result["disease"].eq(disease).astype(float)
            result[f"{disease}_season_sin"] = indicator * result["season_sin"]
            result[f"{disease}_season_cos"] = indicator * result["season_cos"]
        return result

    data = add_seasonal_features(data)
    train = add_seasonal_features(train)
    test = add_seasonal_features(test)
    seasonal_terms = [
        "season_sin", "season_cos",
        "dengue_season_sin", "dengue_season_cos",
        "chikungunya_season_sin", "chikungunya_season_cos",
        "zika_season_sin", "zika_season_cos",
    ]
    model_features = NUMERIC + seasonal_terms + ["disease"]

    preprocessor = ColumnTransformer([
        ("signals_and_season", StandardScaler(), NUMERIC + seasonal_terms),
        ("disease", OneHotEncoder(handle_unknown="ignore"), ["disease"]),
    ])
    # Ridge regularization is used because the two attention signals track a
    # common outbreak process and can be strongly correlated.
    model = make_pipeline(preprocessor, RidgeCV(alphas=np.logspace(-3, 4, 30)))
    model.fit(train[model_features], np.log1p(train[OUTCOME]))
    test["fixed_2024_attention_prediction"] = np.clip(
        np.expm1(model.predict(test[model_features])), 0, None
    )

    # Dynamic seasonal nowcast: refit for every target week using the preceding
    # 52 complete weeks across all three diseases. This includes earlier 2025
    # notifications only after they would have been observed.
    dynamic_predictions = pd.Series(index=test.index, dtype=float)
    for target_date in test["date"].drop_duplicates().sort_values():
        history = data.loc[
            data["date"].lt(target_date) & data["date"].ge(target_date - pd.Timedelta(days=364))
        ].copy()
        dynamic = make_pipeline(preprocessor, RidgeCV(alphas=np.logspace(-3, 4, 30)))
        dynamic.fit(history[model_features], np.log1p(history[OUTCOME]))
        target_rows = test["date"].eq(target_date)
        rows = test.loc[target_rows, model_features]
        dynamic_predictions.loc[target_rows] = np.clip(np.expm1(dynamic.predict(rows)), 0, None)
    test["dynamic_52_week_seasonal_prediction"] = dynamic_predictions
    test.to_csv(HERE / "brazil_arbovirus_2025_attention_predictions.csv", index=False)

    correlations = []
    for (year, disease), group in analysis_data.groupby(["analysis_year", "disease"]):
        for signal in NUMERIC:
            correlations.append({
                "year": year,
                "disease": disease,
                "signal": signal,
                "pearson_r": group[OUTCOME].corr(group[signal]),
                "spearman_r": group[OUTCOME].corr(group[signal], method="spearman"),
            })
    pd.DataFrame(correlations).to_csv(HERE / "brazil_arbovirus_attention_correlations.csv", index=False)

    metric_rows = []
    for model_name, column in [
        ("Fixed 2024 attention + season", "fixed_2024_attention_prediction"),
        ("Dynamic 52-week attention + season", "dynamic_52_week_seasonal_prediction"),
    ]:
        for disease, group in test.groupby("disease"):
            metric_rows.append({"model": model_name, "disease": disease, **scores(group[OUTCOME], group[column])})
        metric_rows.append({"model": model_name, "disease": "pooled", **scores(test[OUTCOME], test[column])})
    metrics = pd.DataFrame(metric_rows)
    metrics.to_csv(HERE / "brazil_arbovirus_2025_attention_metrics.csv", index=False)

    fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
    for ax, disease in zip(axes, ["dengue", "chikungunya", "zika"]):
        group = test.query("disease == @disease")
        ax.plot(group["date"], group[OUTCOME], color="#b22222", lw=2.5, label="SINAN notifications")
        ax.plot(group["date"], group["fixed_2024_attention_prediction"], color="#2563a8", lw=2.1,
                label="Fixed 2024 attention + season")
        ax.plot(group["date"], group["dynamic_52_week_seasonal_prediction"], color="#16803c", lw=2.1,
                label="Dynamic 52-week attention + season")
        ax.set(title=disease.capitalize(), ylabel="Weekly notifications")
        ax.grid(alpha=0.25)
        ax.legend(frameon=False, loc="upper right")
    axes[-1].set_xlabel("Week beginning")
    fig.suptitle("Brazil arbovirus notification nowcasts, 2025", y=0.995)
    fig.text(0.5, 0.01,
             "Outcome: weekly SINAN notification date. Predictors: disease-specific Portuguese attention signals plus cyclic week-of-year seasonality.",
             ha="center", fontsize=9)
    fig.tight_layout(rect=(0, 0.04, 1, 0.98))
    fig.savefig(HERE / "brazil_arbovirus_2025_attention_predictions.png", dpi=180)
    print(metrics.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
