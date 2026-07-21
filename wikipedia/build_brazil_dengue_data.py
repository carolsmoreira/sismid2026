"""Build Brazil 2024--2025 dengue inputs and comparison plots.

Downloads the official SINAN line lists temporarily, aggregates notifications by
symptom-onset week, pulls a single two-year Google Trends series to preserve a
shared 0--100 scale, and fetches Portuguese Wikipedia pageviews.
"""

from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import Request, urlopen
import shutil

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from pytrends.request import TrendReq

from fetch_dengue_pageviews import wiki_fetch


HERE = Path(__file__).resolve().parent
SINAN_URL = "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SINAN/Dengue/csv/DENGBR{year}.csv.zip"


def week_index(year: int) -> pd.DatetimeIndex:
    """Return the Sunday-starting epidemiological weeks that intersect ``year``."""
    start = pd.Timestamp(f"{year}-01-01").to_period("W-SAT").start_time
    end = pd.Timestamp(f"{year}-12-31").to_period("W-SAT").start_time
    return pd.date_range(start, end, freq="W-SUN")


def download(url: str, destination: Path) -> None:
    request = Request(url, headers={"User-Agent": "SISMID2026-course/1.0"})
    with urlopen(request, timeout=120) as response, destination.open("wb") as output:
        shutil.copyfileobj(response, output)


def aggregate_sinan(year: int) -> pd.DataFrame:
    """Aggregate the national line list to weekly notifications by symptom onset."""
    with TemporaryDirectory() as temporary_directory:
        archive = Path(temporary_directory) / f"DENGBR{year}.csv.zip"
        print(f"Downloading SINAN dengue {year} line list …")
        download(SINAN_URL.format(year=year), archive)
        counts = []
        for chunk in pd.read_csv(archive, compression="zip", usecols=["DT_SIN_PRI"], chunksize=250_000):
            onset = pd.to_datetime(chunk["DT_SIN_PRI"], format="%Y-%m-%d", errors="coerce")
            onset = onset[onset.dt.year.eq(year)]
            counts.append(onset.dt.to_period("W-SAT").dt.start_time.value_counts())
    weekly = pd.concat(counts).groupby(level=0).sum()
    index = week_index(year)
    return pd.DataFrame({
        "date": index,
        "sinan_notified_cases": weekly.reindex(index, fill_value=0).astype(int).to_numpy(),
    })


def fetch_google_trends() -> pd.DataFrame:
    """Fetch a common-scale weekly Brazil series for 2024 and 2025."""
    trends = TrendReq(hl="en-US", tz=0, timeout=(10, 30), retries=1, backoff_factor=0.2)
    trends.build_payload(["dengue"], timeframe="2024-01-01 2025-12-31", geo="BR")
    return trends.interest_over_time().reset_index()[["date", "dengue"]]


def add_wikipedia(data: pd.DataFrame, wiki: pd.DataFrame) -> pd.DataFrame:
    return pd.merge_asof(data.sort_values("date"), wiki.sort_values("date"), on="date", direction="backward")


def plot_2024(data: pd.DataFrame) -> None:
    fig, (ax_index, ax_cases) = plt.subplots(2, 1, figsize=(12, 8.5), sharex=True,
                                              gridspec_kw={"height_ratios": [1, 1.05]})
    def indexed(series: pd.Series) -> pd.Series:
        return series / series.max() * 100

    ax_index.plot(data["date"], indexed(data["sinan_notified_cases"]), color="#b22222", lw=2.5,
                  label="SINAN dengue notifications")
    ax_index.plot(data["date"], indexed(data["dengue"]), color="#1f77b4", lw=2.5,
                  label='Google Trends: "dengue" (Brazil)')
    ax_index.step(data["date"], indexed(data["dengue_pt"]), where="post", color="#16803c", lw=2.5,
                  label="Portuguese Wikipedia: Dengue")
    ax_index.set(title="Brazil dengue, 2024: cases and online attention signals",
                 ylabel="Index (each series scaled to peak = 100)", ylim=(0, 108))
    ax_index.grid(alpha=0.25)
    ax_index.legend(ncol=3, frameon=False, loc="upper right", fontsize=9)

    ax_cases.bar(data["date"], data["sinan_notified_cases"], width=5.2, color="#b22222", alpha=0.72,
                 label="Weekly SINAN notifications")
    ax_trends = ax_cases.twinx()
    ax_trends.plot(data["date"], data["dengue"], color="#1f77b4", lw=2.5,
                   label='Google Trends: "dengue"')
    ax_cases.set(ylabel="Weekly SINAN notifications", xlabel="Week beginning")
    ax_trends.set(ylabel="Google Trends interest (0–100)", ylim=(0, 105))
    ax_cases.grid(axis="y", alpha=0.25)
    handles, labels = ax_cases.get_legend_handles_labels()
    handles2, labels2 = ax_trends.get_legend_handles_labels()
    ax_cases.legend(handles + handles2, labels + labels2, frameon=False, loc="upper right")
    ax_cases.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax_cases.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    fig.text(0.5, 0.01, "SINAN: Open Data SUS. Google Trends and Wikipedia are attention signals; Wikipedia is monthly.",
             ha="center", fontsize=9)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(HERE / "brazil_dengue_sinan_wikipedia_google_trends_2024.png", dpi=180)


def plot_wikipedia_vs_cases(data: pd.DataFrame) -> None:
    """Create the direct 2024 national Wikipedia-versus-SINAN comparison."""
    fig, ax_cases = plt.subplots(figsize=(12, 5.5))
    ax_cases.bar(data["date"], data["sinan_notified_cases"], width=5.2, color="#b22222", alpha=0.72,
                 label="Weekly dengue notifications (Brazil)")
    ax_cases.set(ylabel="Weekly SINAN notifications", xlabel="Week beginning",
                 title="Brazil dengue, 2024: SINAN notifications and Portuguese Wikipedia interest")
    ax_cases.grid(axis="y", alpha=0.25)
    ax_wiki = ax_cases.twinx()
    ax_wiki.step(data["date"], data["dengue_pt"], where="post", color="#16803c", lw=2.5,
                 label="Portuguese Wikipedia pageviews (monthly)")
    ax_wiki.set_ylabel("Monthly Portuguese Wikipedia pageviews", color="#16803c")
    ax_wiki.tick_params(axis="y", labelcolor="#16803c")
    handles, labels = ax_cases.get_legend_handles_labels()
    handles2, labels2 = ax_wiki.get_legend_handles_labels()
    ax_cases.legend(handles + handles2, labels + labels2, frameon=False, loc="upper right")
    ax_cases.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax_cases.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    fig.text(0.5, 0.01, "Wikipedia pageviews are monthly and are repeated across each month's weeks.",
             ha="center", fontsize=9)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(HERE / "brazil_wikipedia_pt_vs_weekly_cases_2024.png", dpi=180)


def main() -> None:
    google = fetch_google_trends()
    wiki = wiki_fetch("Dengue", "pt.wikipedia", start="2023120100", end="2026010100")
    wiki = wiki[wiki["date"].lt("2026-01-01")].rename(columns={"views": "dengue_pt"})
    wiki.to_csv(HERE / "brazil_wikipedia_pt_2023_2025_monthly.csv", index=False)

    for year in (2024, 2025):
        cases = aggregate_sinan(year)
        cases.to_csv(HERE / f"brazil_sinan_dengue_{year}_weekly.csv", index=False)
        trends = google[google["date"].between(cases["date"].min(), cases["date"].max())]
        trends.to_csv(HERE / f"brazil_google_trends_dengue_{year}_weekly.csv", index=False)

    data_2024 = pd.read_csv(HERE / "brazil_sinan_dengue_2024_weekly.csv", parse_dates=["date"])
    trends_2024 = pd.read_csv(HERE / "brazil_google_trends_dengue_2024_weekly.csv", parse_dates=["date"])
    data_2024 = add_wikipedia(data_2024.merge(trends_2024, on="date"), wiki)
    plot_wikipedia_vs_cases(data_2024)
    plot_2024(data_2024)
    print("Saved national weekly inputs and the 2024 comparison plot to", HERE)


if __name__ == "__main__":
    main()
