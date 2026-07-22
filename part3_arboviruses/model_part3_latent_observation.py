"""Joint latent-infection / observation model for Brazil arbovirus notifications.

Latent infections follow a seasonal renewal process with susceptible depletion.
Observed SINAN notifications are a delayed, disease-specific ascertained fraction
of latent infections. The model is fitted separately by disease on 2024 weekly
notification dates, then recursively forecasts the same 52 full weeks of 2025.

Important: notification counts alone weakly identify latent-infection scale and
ascertainment. We anchor susceptible population to the 2022 IBGE national census
and apply a weak regularization to the reporting fraction; fitted fractions are
therefore model-dependent sensitivity parameters, not estimated surveillance
coverage.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit, logsumexp
from sklearn.metrics import mean_absolute_error, mean_squared_error


HERE = Path(__file__).resolve().parent
OUTCOME = "sinan_notifications"
BRAZIL_CENSUS_2022_POPULATION = 203_062_512
GENERATION_WEIGHTS = np.array([0.55, 0.30, 0.15])
N_DELAYS = 4  # same-week through three-week reporting delay


def seasonal_terms(date: pd.Timestamp) -> tuple[float, float]:
    phase = 2 * np.pi * date.isocalendar().week / 52.18
    return np.sin(phase), np.cos(phase)


def latent_path(dates: list[pd.Timestamp], params: np.ndarray) -> np.ndarray:
    """Generate a deterministic seasonal renewal path of latent infections."""
    beta0, beta_sin, beta_cos, log_initial_infections = params[:4]
    latent = []
    for index, date in enumerate(dates):
        if index < len(GENERATION_WEIGHTS):
            infections = np.exp(log_initial_infections)
        else:
            sin_term, cos_term = seasonal_terms(date)
            reproduction = np.exp(np.clip(beta0 + beta_sin * sin_term + beta_cos * cos_term, -9, 4))
            recent = np.asarray(latent[-len(GENERATION_WEIGHTS):][::-1])
            infectious_pressure = float(np.dot(GENERATION_WEIGHTS, recent))
            susceptible_fraction = max(1e-7, 1 - sum(latent) / BRAZIL_CENSUS_2022_POPULATION)
            infections = max(1e-7, reproduction * infectious_pressure * susceptible_fraction)
        latent.append(infections)
    return np.asarray(latent)


def unpack_observation(params: np.ndarray) -> tuple[float, np.ndarray]:
    # Bounded logit prevents a numerically unidentifiable near-zero/one fraction.
    ascertainment = expit(params[4])
    delay_logits = np.r_[params[5:], 0.0]
    delay_weights = np.exp(delay_logits - logsumexp(delay_logits))
    return ascertainment, delay_weights


def expected_notifications(latent: np.ndarray, ascertainment: float, delays: np.ndarray) -> np.ndarray:
    expected = np.zeros_like(latent)
    for t in range(len(latent)):
        relevant = latent[max(0, t - N_DELAYS + 1):t + 1][::-1]
        expected[t] = ascertainment * np.dot(delays[:len(relevant)], relevant)
    return np.clip(expected, 1e-7, None)


def fit_model(train: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    dates = train["date"].tolist()
    observed = train[OUTCOME].to_numpy(dtype=float)

    def objective(params: np.ndarray) -> float:
        latent = latent_path(dates, params)
        ascertainment, delays = unpack_observation(params)
        expected = expected_notifications(latent, ascertainment, delays)
        poisson_nll = np.sum(expected - observed * np.log(expected))
        # Weak prior/penalty anchors the otherwise near-nonidentifiable reporting
        # fraction around 2% on the logit scale; it is deliberately reported.
        ascertainment_penalty = 0.05 * (params[4] - np.log(0.02 / 0.98)) ** 2
        return float(poisson_nll + ascertainment_penalty)

    initial_reporting = 0.02
    initial_infections = max(observed[:4].mean() / initial_reporting, 10)
    initial = np.array([
        0.0, 0.0, 0.0, np.log(initial_infections), np.log(initial_reporting / (1 - initial_reporting)),
        0.0, 0.0, 0.0,
    ])
    result = minimize(
        objective, initial, method="L-BFGS-B",
        bounds=[(-6, 3), (-4, 4), (-4, 4), (np.log(1), np.log(2e8)), (-11, -0.1),
                (-8, 8), (-8, 8), (-8, 8)],
        options={"maxiter": 5_000},
    )
    if not result.success:
        raise RuntimeError(f"Latent-observation optimization failed: {result.message}")
    latent = latent_path(dates, result.x)
    ascertainment, delays = unpack_observation(result.x)
    return result.x, latent, expected_notifications(latent, ascertainment, delays)


def forecast(train_dates: list[pd.Timestamp], test_dates: list[pd.Timestamp], params: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    all_dates = train_dates + test_dates
    all_latent = latent_path(all_dates, params)
    ascertainment, delays = unpack_observation(params)
    all_expected = expected_notifications(all_latent, ascertainment, delays)
    return all_latent[-len(test_dates):], all_expected[-len(test_dates):]


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

    predictions, fit_rows, score_rows = [], [], []
    for disease in ("dengue", "chikungunya", "zika"):
        training = train.query("disease == @disease").sort_values("date")
        testing = test.query("disease == @disease").sort_values("date").copy()
        params, train_latent, train_expected = fit_model(training)
        test_latent, test_expected = forecast(training["date"].tolist(), testing["date"].tolist(), params)
        ascertainment, delays = unpack_observation(params)
        testing["latent_infections"] = test_latent
        testing["latent_observation_prediction"] = test_expected
        predictions.append(testing)
        fit_rows.append({
            "disease": disease,
            "ascertainment_fraction": ascertainment,
            "same_week_delay_weight": delays[0],
            "one_week_delay_weight": delays[1],
            "two_week_delay_weight": delays[2],
            "three_week_delay_weight": delays[3],
            "R_log_intercept": params[0], "R_sin": params[1], "R_cos": params[2],
        })

    predicted = pd.concat(predictions, ignore_index=True)
    predicted.to_csv(HERE / "brazil_arbovirus_2025_latent_observation_predictions.csv", index=False)
    pd.DataFrame(fit_rows).to_csv(HERE / "brazil_arbovirus_latent_observation_fit_parameters.csv", index=False)
    for disease, group in predicted.groupby("disease"):
        score_rows.append({"disease": disease, **metrics(group[OUTCOME], group["latent_observation_prediction"])})
    score_rows.append({"disease": "pooled", **metrics(predicted[OUTCOME], predicted["latent_observation_prediction"])})
    scores = pd.DataFrame(score_rows)
    scores.to_csv(HERE / "brazil_arbovirus_2025_latent_observation_metrics.csv", index=False)

    fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
    for ax, disease in zip(axes, ("dengue", "chikungunya", "zika")):
        group = predicted.query("disease == @disease")
        ax.plot(group["date"], group[OUTCOME], color="#b22222", lw=2.5, label="SINAN notifications")
        ax.plot(group["date"], group["latent_observation_prediction"], color="#d95f02", lw=2.2,
                label="Latent-infection observation model")
        ax.set(title=disease.capitalize(), ylabel="Weekly notifications")
        ax.grid(alpha=0.25)
        ax.legend(frameon=False)
    axes[-1].set_xlabel("Week beginning")
    fig.suptitle("Latent-infection observation forecasts, Brazil 2025", y=0.995)
    fig.text(0.5, 0.01,
             "Fit on 2024 only. Latent infections: seasonal renewal; observations: disease-specific reporting fraction and 0–3 week delay distribution.",
             ha="center", fontsize=9)
    fig.tight_layout(rect=(0, 0.04, 1, 0.98))
    fig.savefig(HERE / "brazil_arbovirus_2025_latent_observation_predictions.png", dpi=180)
    print(scores.round(2).to_string(index=False))
    print("\nFitted observation parameters (model-dependent):")
    print(pd.DataFrame(fit_rows).round(3).to_string(index=False))


if __name__ == "__main__":
    main()
