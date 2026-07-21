"""Plot the Rio 2025 nowcast before and after adding Wikipedia pageviews.

The baseline is read from the repository revision immediately before the
Wikipedia predictor was added.  Both versions are scored on the same 52 full
weeks of 2025, avoiding the partial week beginning 2025-12-28.
"""

from io import StringIO
from pathlib import Path
import subprocess

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
BASELINE_REVISION = "e4f74a3"
BASELINE_FILE = "rj_trends/rio_dengue_2025_mlr_dynamic_predictions.csv"


def load_baseline() -> pd.DataFrame:
    """Load the committed Google-Trends-only predictions."""
    result = subprocess.run(
        ["git", "show", f"{BASELINE_REVISION}:{BASELINE_FILE}"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return pd.read_csv(StringIO(result.stdout), parse_dates=["date"])


def score(actual: pd.Series, predicted: pd.Series) -> dict[str, float]:
    return {
        "mae": mean_absolute_error(actual, predicted),
        "rmse": mean_squared_error(actual, predicted) ** 0.5,
        "pearson_r": actual.corr(predicted),
    }


def main() -> None:
    old = load_baseline()
    new = pd.read_csv(
        HERE / "rio_dengue_2025_mlr_dynamic_predictions.csv", parse_dates=["date"]
    )
    data = old.merge(new, on="date", suffixes=("_old", "_new"))
    data = data.query("date <= '2025-12-21'").copy()
    actual = data["sinan_notified_cases_new"]

    models = {
        "Fixed 2024 MLR": ("fixed_mlr_prediction_old", "fixed_mlr_prediction_new"),
        "Dynamic 52-week MLR": (
            "dynamic_52_week_prediction_old",
            "dynamic_52_week_prediction_new",
        ),
    }
    rows = []
    for model, (old_col, new_col) in models.items():
        for version, column in [("Google Trends only", old_col), ("Trends + Wikipedia", new_col)]:
            rows.append({"model": model, "version": version, **score(actual, data[column])})
    metrics = pd.DataFrame(rows)
    metrics.to_csv(HERE / "rio_dengue_2025_nowcast_version_comparison_metrics.csv", index=False)

    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    for ax, (model, (old_col, new_col)) in zip(axes, models.items()):
        ax.plot(data["date"], actual, color="#b22222", lw=2.7, label="SINAN notified cases")
        ax.plot(data["date"], data[old_col], color="#6c757d", lw=2, ls="--",
                label="Previous: Google Trends only")
        ax.plot(data["date"], data[new_col], color="#2ca02c", lw=2.2,
                label="Current: Trends + Wikipedia")
        ax.set(title=model, ylabel="Notified dengue cases")
        ax.grid(alpha=0.25)
        ax.legend(frameon=False, ncol=3, loc="upper right")
    axes[-1].set_xlabel("Week beginning")
    fig.suptitle("Rio dengue nowcast, 2025: previous vs Wikipedia-enhanced models", y=0.98)
    fig.text(
        0.5,
        0.01,
        "Both versions are evaluated on the same 52 complete 2025 weeks. "
        "Wikipedia uses monthly Portuguese Dengue pageviews as a Brazil-oriented proxy.",
        ha="center",
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.96))
    fig.savefig(HERE / "rio_dengue_2025_nowcast_version_comparison.png", dpi=180)

    print(metrics.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
