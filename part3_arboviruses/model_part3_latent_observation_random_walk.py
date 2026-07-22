"""Latent-infection observation model with a Gaussian random walk in log R.

This extends the seasonal latent-observation comparator by allowing the
log-reproduction number to make small Gaussian four-week departures from its
seasonal mean during the 2024 fit.  The random-walk innovation standard
deviation is fixed before seeing 2025 (0.15 on the log-R scale) to keep the
weekly deviations from absorbing all of the outcome variation.  At the 2025
forecast origin the final fitted deviation is carried forward; future
innovations have mean zero, so the forecast continues with the seasonal curve.
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
N_DELAYS = 4
RANDOM_WALK_SD = 0.15
N_RANDOM_WALK_STATES = 13


def seasonal_terms(date: pd.Timestamp) -> tuple[float, float]:
    phase = 2 * np.pi * date.isocalendar().week / 52.18
    return np.sin(phase), np.cos(phase)


def latent_path(dates: list[pd.Timestamp], params: np.ndarray, train_weeks: int) -> np.ndarray:
    """Generate latent infections; retain the final fitted RW state in forecast."""
    beta0, beta_sin, beta_cos, log_initial_infections = params[:4]
    rw_states = params[8:8 + N_RANDOM_WALK_STATES]
    state_times = np.linspace(0, train_weeks - 1, N_RANDOM_WALK_STATES)
    latent = []
    for index, date in enumerate(dates):
        # Linear interpolation provides a weekly log-R value while keeping the
        # number of random-walk states supportable by a single training year.
        rw_state = np.interp(min(index, train_weeks - 1), state_times, rw_states)
        if index < len(GENERATION_WEIGHTS):
            infections = np.exp(log_initial_infections)
        else:
            sin_term, cos_term = seasonal_terms(date)
            log_r = beta0 + beta_sin * sin_term + beta_cos * cos_term + rw_state
            reproduction = np.exp(np.clip(log_r, -9, 4))
            recent = np.asarray(latent[-len(GENERATION_WEIGHTS):][::-1])
            pressure = float(np.dot(GENERATION_WEIGHTS, recent))
            susceptible_fraction = max(1e-7, 1 - sum(latent) / BRAZIL_CENSUS_2022_POPULATION)
            infections = max(1e-7, reproduction * pressure * susceptible_fraction)
        latent.append(infections)
    return np.asarray(latent)


def unpack_observation(params: np.ndarray) -> tuple[float, np.ndarray]:
    ascertainment = expit(params[4])
    delay_logits = np.r_[params[5:8], 0.0]
    delays = np.exp(delay_logits - logsumexp(delay_logits))
    return ascertainment, delays


def expected_notifications(latent: np.ndarray, ascertainment: float, delays: np.ndarray) -> np.ndarray:
    expected = np.zeros_like(latent)
    for t in range(len(latent)):
        relevant = latent[max(0, t - N_DELAYS + 1):t + 1][::-1]
        expected[t] = ascertainment * np.dot(delays[:len(relevant)], relevant)
    return np.clip(expected, 1e-7, None)


def fit_model(train: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    dates = train["date"].tolist()
    observed = train[OUTCOME].to_numpy(dtype=float)
    train_weeks = len(train)

    def objective(params: np.ndarray) -> float:
        latent = latent_path(dates, params, train_weeks)
        ascertainment, delays = unpack_observation(params)
        expected = expected_notifications(latent, ascertainment, delays)
        poisson_nll = np.sum(expected - observed * np.log(expected))
        # Gaussian N(0, RANDOM_WALK_SD^2) innovations and weak N(0, SD^2)
        # prior for the initial deviation implement the random-walk penalty.
        states = params[8:]
        rw_penalty = 0.5 * (states[0] / RANDOM_WALK_SD) ** 2
        rw_penalty += 0.5 * np.sum((np.diff(states) / RANDOM_WALK_SD) ** 2)
        ascertainment_penalty = 0.05 * (params[4] - np.log(0.02 / 0.98)) ** 2
        return float(poisson_nll + rw_penalty + ascertainment_penalty)

    initial_reporting = 0.02
    initial_infections = max(observed[:4].mean() / initial_reporting, 10)
    initial = np.r_[
        [0.0, 0.0, 0.0, np.log(initial_infections), np.log(initial_reporting / (1 - initial_reporting)),
         0.0, 0.0, 0.0],
        np.zeros(N_RANDOM_WALK_STATES),
    ]
    bounds = [(-6, 3), (-4, 4), (-4, 4), (np.log(1), np.log(2e8)), (-11, -0.1),
              (-8, 8), (-8, 8), (-8, 8)] + [(-3, 3)] * N_RANDOM_WALK_STATES
    result = minimize(objective, initial, method="L-BFGS-B", bounds=bounds,
                      options={"maxiter": 10_000, "maxfun": 100_000})
    if not result.success:
        raise RuntimeError(f"Random-walk latent optimization failed: {result.message}")
    latent = latent_path(dates, result.x, train_weeks)
    ascertainment, delays = unpack_observation(result.x)
    return result.x, latent, expected_notifications(latent, ascertainment, delays)


def forecast(train_dates: list[pd.Timestamp], test_dates: list[pd.Timestamp], params: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    all_latent = latent_path(train_dates + test_dates, params, len(train_dates))
    ascertainment, delays = unpack_observation(params)
    expected = expected_notifications(all_latent, ascertainment, delays)
    return all_latent[-len(test_dates):], expected[-len(test_dates):]


def metrics(actual: pd.Series, predicted: pd.Series) -> dict[str, float]:
    return {"mae": mean_absolute_error(actual, predicted),
            "rmse": mean_squared_error(actual, predicted) ** 0.5,
            "pearson_r": actual.corr(predicted),
            "observed_total": actual.sum(), "predicted_total": predicted.sum()}


def main() -> None:
    data = pd.read_csv(HERE / "brazil_arbovirus_notification_attention_2024_2025_weekly.csv", parse_dates=["date"])
    train = data.query("date >= '2023-12-31' and date <= '2024-12-22'").copy()
    test = data.query("date >= '2024-12-29' and date <= '2025-12-21'").copy()
    predictions, fit_rows = [], []
    for disease in ("dengue", "chikungunya", "zika"):
        training = train.query("disease == @disease").sort_values("date")
        testing = test.query("disease == @disease").sort_values("date").copy()
        params, _, _ = fit_model(training)
        test_latent, test_expected = forecast(training["date"].tolist(), testing["date"].tolist(), params)
        ascertainment, delays = unpack_observation(params)
        states = params[8:]
        testing["latent_infections_random_walk"] = test_latent
        testing["latent_observation_random_walk_prediction"] = test_expected
        predictions.append(testing)
        fit_rows.append({"disease": disease, "random_walk_sd": RANDOM_WALK_SD,
                         "random_walk_interval_weeks": 4, "final_log_R_deviation": states[-1],
                         "ascertainment_fraction": ascertainment,
                         "same_week_delay_weight": delays[0], "one_week_delay_weight": delays[1],
                         "two_week_delay_weight": delays[2], "three_week_delay_weight": delays[3],
                         "R_log_intercept": params[0], "R_sin": params[1], "R_cos": params[2]})

    predicted = pd.concat(predictions, ignore_index=True)
    predicted.to_csv(HERE / "brazil_arbovirus_2025_latent_observation_random_walk_predictions.csv", index=False)
    pd.DataFrame(fit_rows).to_csv(HERE / "brazil_arbovirus_latent_observation_random_walk_fit_parameters.csv", index=False)
    score_rows = [{"disease": disease, **metrics(group[OUTCOME], group["latent_observation_random_walk_prediction"])}
                  for disease, group in predicted.groupby("disease")]
    score_rows.append({"disease": "pooled", **metrics(predicted[OUTCOME], predicted["latent_observation_random_walk_prediction"])})
    scores = pd.DataFrame(score_rows)
    scores.to_csv(HERE / "brazil_arbovirus_2025_latent_observation_random_walk_metrics.csv", index=False)

    fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
    for ax, disease in zip(axes, ("dengue", "chikungunya", "zika")):
        group = predicted.query("disease == @disease")
        ax.plot(group["date"], group[OUTCOME], color="#b22222", lw=2.5, label="SINAN notifications")
        ax.plot(group["date"], group["latent_observation_random_walk_prediction"], color="#1b9e77", lw=2.2,
                label="Latent-observation + Gaussian random walk")
        ax.set(title=disease.capitalize(), ylabel="Weekly notifications")
        ax.grid(alpha=0.25); ax.legend(frameon=False)
    axes[-1].set_xlabel("Week beginning")
    fig.suptitle("Latent-observation random-walk forecasts, Brazil 2025", y=0.995)
    fig.text(0.5, 0.01, "Fit on 2024 only. Log R has a seasonal mean plus Gaussian four-week random-walk deviations (SD 0.15); future innovations have mean zero.", ha="center", fontsize=9)
    fig.tight_layout(rect=(0, 0.04, 1, 0.98))
    fig.savefig(HERE / "brazil_arbovirus_2025_latent_observation_random_walk_predictions.png", dpi=180)
    print(scores.round(2).to_string(index=False))
    print("\nFitted random-walk and observation parameters:")
    print(pd.DataFrame(fit_rows).round(3).to_string(index=False))


if __name__ == "__main__":
    main()
