"""Add Portuguese Wikipedia dengue pageviews to the 2024 Rio comparison plot."""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


HERE = Path(__file__).resolve().parent
WIKI_CSV = HERE.parent / "wikipedia" / "dengue_pageviews_en_es_pt.csv"
CASES_CSV = HERE / "rio_dengue_trends_vs_sinan_2024_weekly.csv"
OUTPUT = HERE / "rio_dengue_trends_vs_sinan_2024.png"


def peak_index(series: pd.Series) -> pd.Series:
    """Express a series as an index whose peak is 100."""
    return series / series.max() * 100


def main() -> None:
    rio = pd.read_csv(CASES_CSV, parse_dates=["date"])
    wiki = pd.read_csv(WIKI_CSV, parse_dates=["date"])[["date", "dengue_pt"]]

    # Pageviews are monthly.  Carry each month's value across its weekly observations.
    data = pd.merge_asof(
        rio.sort_values("date"), wiki.sort_values("date"), on="date", direction="backward"
    )
    data["dengue_pt"] = data["dengue_pt"].bfill()

    fig, (ax_index, ax_cases) = plt.subplots(2, 1, figsize=(12, 9), sharex=True)
    fig.subplots_adjust(hspace=0.06)

    ax_index.plot(data["date"], peak_index(data["dengue"]), color="#1f77b4", lw=2.5,
                  label="Google Trends: dengue")
    ax_index.plot(data["date"], peak_index(data["sinan_notified_cases"]), color="#b22222", lw=2.5,
                  label="SINAN/DATASUS: notified dengue cases")
    ax_index.plot(data["date"], peak_index(data["dengue_pt"]), color="#2ca02c", lw=2.5,
                  label="Wikipedia Portuguese: Dengue (Brazil proxy)")
    ax_index.set(
        title="Rio de Janeiro, 2024: dengue attention signals vs notified cases",
        ylabel="Index (each series scaled to peak = 100)",
    )
    ax_index.grid(alpha=0.28)
    ax_index.legend(frameon=False, loc="upper right")

    ax_cases.bar(data["date"], data["sinan_notified_cases"], width=5, color="#b22222", alpha=0.8,
                 label="Notified cases (left axis)")
    ax_trends = ax_cases.twinx()
    ax_trends.plot(data["date"], data["dengue"], color="#1f77b4", lw=2.5,
                   label="Google Trends: dengue (right axis)")
    ax_cases.set(xlabel="Week beginning", ylabel="Notified cases")
    ax_trends.set_ylabel("Google Trends interest (0–100)", color="#1f77b4")
    ax_cases.grid(axis="y", alpha=0.28)
    handles = ax_cases.get_legend_handles_labels()[0] + ax_trends.get_legend_handles_labels()[0]
    labels = ax_cases.get_legend_handles_labels()[1] + ax_trends.get_legend_handles_labels()[1]
    ax_cases.legend(handles, labels, frameon=False, loc="upper right")

    fig.text(
        0.5, 0.01,
        "Portuguese Wikipedia pageviews are monthly and represent a Brazil-oriented access proxy, not Rio-only activity.\n"
        "SINAN source: Open Data SUS dengue 2024 extract, accessed 2026-07-20.",
        ha="center", va="bottom", fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(OUTPUT, dpi=180)
    print(f"Saved {OUTPUT}")


if __name__ == "__main__":
    main()
