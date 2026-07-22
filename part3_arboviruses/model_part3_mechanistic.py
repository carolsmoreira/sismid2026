"""Seasonal renewal-model comparator for 2025 arbovirus notification nowcasts.

This is a deliberately simple mechanistic baseline. It treats weekly notification
counts as a proxy for infectious activity and uses a discrete renewal process with
seasonal transmission and an estimated effective susceptible pool. It is not a
fully observed infection-transmission model because SINAN notification dates are
affected by care seeking and reporting delays.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from sklearn.metrics import mean_absolute_error, mean_squared_error


HERE = Path(__file__).resolve().parent
OUTCOME = "sinan_notifications"
# Weekly infectiousness profile. It gives most weight to the previous week while
# retaining short two- and three-week transmission memory.
GENERATION_WEIGHTS = np.array([0.55, 0.30, 0.15])


def seasonal_terms(date: pd.Timestamp) -> tuple[float, float]:
    phase = 2 * np.pi * date.isocalendar().week / 52.18
    return np.sin(phase), np.cos(phase)


def pressure(history: list[float]) -> float:
    recent = np.asarray(history[-len(GENERATION_WEIGHTS):][::-1], dtype=float)
    weights = GENERATION_WEIGHTS[:len(recent)]
    return float(np.dot(weights, recent))


def fit_renewal(train: pd.DataFrame) -> tuple[np.ndarray, float]:
    """Fit seasonal reproduction terms and effective notification-scale pool."""
    values = train[OUTCOME].to_numpy(dtype=float)
    dates = train["date"].tolist()
    total = values.sum()

    def objective(params: np.ndarray) -> float:
        beta0, beta_sin, beta_cos, log_extra_pool = params
        effective_pool = total + np.exp(log_extra_pool)
        losses = []
        for t in range(len(values)):
            if t < len(GENERATION_WEIGHTS):
                continue
            sin_term, cos_term = seasonal_terms(dates[t])
            reproduction = np.exp(np.clip(beta0 + beta_sin * sin_term + beta_cos * cos_term, -10, 10))
            susceptible_fraction = max(1e-6, 1 - values[:t].sum() / effective_pool)
            expected = max(1e-6, reproduction * pressure(values[:t].tolist()) * susceptible_fraction)
            # Poisson negative log likelihood up to a y!-only constant.
            losses.append(expected - values[t] * np.log(expected))
        return float(np.sum(losses))

    initial_pressure = np.median([pressure(values[:t].tolist()) for t in range(3, len(values))])
    initial = np.array([np.log(max(values.mean(), 1) / max(initial_pressure, 1)), 0, 0, np.log(max(total, 1))])
    result = minimize(
        objective, initial, method="L-BFGS-B",
        bounds=[(-8, 8), (-5, 5), (-5, 5), (np.log(1), np.log(1e10))],
    )
    if not result.success:
        raise RuntimeError(f"Renewal-model optimization failed: {result.message}")
    return result.x[:3], total + np.exp(result.x[3])


def forecast(train: pd.DataFrame, test: pd.DataFrame, params: np.ndarray, effective_pool: float) -> np.ndarray:
    history = train[OUTCOME].astype(float).tolist()
    predictions = []
    for date in test["date"]:
        sin_term, cos_term = seasonal_terms(date)
        reproduction = np.exp(np.clip(params[0] + params[1] * sin_term + params[2] * cos_term, -10, 10))
        susceptible_fraction = max(1e-6, 1 - sum(history) / effective_pool)
        expected = max(0, reproduction * pressure(history) * susceptible_fraction)
        predictions.append(expected)
        # Recursive forecast: do not use the current/future observed 2025 count.
        history.append(expected)
    return np.asarray(predictions)


def metrics(actual: pd.Series, predicted: pd.Series) -> dict[str, float]:
    return {
        "mae": mean_absolute_error(actual, predicted),
        "rmse": mean_squared_error(actual, predicted) ** 0.5,
        "pearson_r": actual.corr(predicted),
        "observed_total": actual.sum(),
        "predicted_total": predicted.sum(),
    }


def main() -> None:
    data = pd.read_csv(HERE / "brazil_arbovirus_notification_attention_2024_2025_weekly.csv", parse_dates=["date"])
    train = data.query("date >= '2023-12-31' and date <= '2024-12-22'").copy()
    test = data.query("date >= '2024-12-29' and date <= '2025-12-21'").copy()

    predictions = []
    fit_rows = []
    for disease in ("dengue", "chikungunya", "zika"):
        train_disease = train.query("disease == @disease").sort_values("date")
        test_disease = test.query("disease == @disease").sort_values("date").copy()
        params, pool = fit_renewal(train_disease)
        test_disease["seasonal_renewal_prediction"] = forecast(train_disease, test_disease, params, pool)
        predictions.append(test_disease)
        fit_rows.append({
            "disease": disease, "log_R_intercept": params[0], "R_sin": params[1], "R_cos": params[2],
            "effective_notification_pool": pool,
        })

    predicted = pd.concat(predictions, ignore_index=True)
    predicted.to_csv(HERE / "brazil_arbovirus_2025_mechanistic_predictions.csv", index=False)
    pd.DataFrame(fit_rows).to_csv(HERE / "brazil_arbovirus_mechanistic_fit_parameters.csv", index=False)

    metric_rows = []
    for disease, group in predicted.groupby("disease"):
        metric_rows.append({"disease": disease, **metrics(group[OUTCOME], group["seasonal_renewal_prediction"])})
    metric_rows.append({"disease": "pooled", **metrics(predicted[OUTCOME], predicted["seasonal_renewal_prediction"])})
    score_table = pd.DataFrame(metric_rows)
    score_table.to_csv(HERE / "brazil_arbovirus_2025_mechanistic_metrics.csv", index=False)

    fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
    for ax, disease in zip(axes, ("dengue", "chikungunya", "zika")):
        group = predicted.query("disease == @disease")
        ax.plot(group["date"], group[OUTCOME], color="#b22222", lw=2.5, label="SINAN notifications")
        ax.plot(group["date"], group["seasonal_renewal_prediction"], color="#7b3294", lw=2.2,
                label="Seasonal renewal model")
        ax.set(title=disease.capitalize(), ylabel="Weekly notifications")
        ax.grid(alpha=0.25)
        ax.legend(frameon=False)
    axes[-1].set_xlabel("Week beginning")
    fig.suptitle("Mechanistic seasonal-renewal forecasts, Brazil 2025", y=0.995)
    fig.text(0.5, 0.01,
             "Fit on 2024 notification weeks only; recursively forecast 2025. Notifications are used as a proxy for infectious activity.",
             ha="center", fontsize=9)
    fig.tight_layout(rect=(0, 0.04, 1, 0.98))
    fig.savefig(HERE / "brazil_arbovirus_2025_mechanistic_predictions.png", dpi=180)
    print(score_table.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
