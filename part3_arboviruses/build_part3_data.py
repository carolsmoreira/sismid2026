"""Build 2024--2025 Brazil arbovirus notification and attention-signal inputs.

The outcome is weekly SINAN *notification date* (DT_NOTIFIC), not symptom-onset
date. This matches the Part III question: whether the initial registration in
the surveillance system covaries with disease-specific public-information use.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import quote
from urllib.request import Request, urlopen

import pandas as pd
import requests
from pytrends.request import TrendReq


HERE = Path(__file__).resolve().parent
USER_AGENT = "SISMID2026-course/1.0"
DISEASES = {
    "dengue": {
        "sinan_url": "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SINAN/Dengue/csv/DENGBR{year2}.csv.zip",
        "format": "csv",
        "google_term": "dengue",
        "wiki_article": "Dengue",
    },
    "chikungunya": {
        "sinan_url": "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SINAN/Chikungunya/csv/CHIKBR{year2}.csv.zip",
        "format": "csv",
        "google_term": "chikungunya",
        "wiki_article": "Chicungunha",
    },
    "zika": {
        "sinan_url": "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SINAN/Zikavirus/json/ZIKABR{year2}.json.zip",
        "format": "json",
        "google_term": "zika",
        "wiki_article": "Febre_zika",
    },
}


def download(url: str, destination: Path) -> None:
    # requests is more reliable than urllib for the Open Data SUS S3 endpoint.
    with requests.get(url, headers={"User-Agent": USER_AGENT}, stream=True, timeout=180) as response:
        response.raise_for_status()
        with destination.open("wb") as output:
            for block in response.iter_content(chunk_size=1024 * 1024):
                if block:
                    output.write(block)


def week_index(year: int) -> pd.DatetimeIndex:
    start = pd.Timestamp(f"{year}-01-01").to_period("W-SAT").start_time
    end = pd.Timestamp(f"{year}-12-31").to_period("W-SAT").start_time
    return pd.date_range(start, end, freq="W-SUN")


def dates_to_week_counts(raw_dates: pd.Series, year: int) -> pd.Series:
    """Parse notification dates and return counts keyed by Sunday-starting week."""
    dates = pd.to_datetime(raw_dates, errors="coerce", dayfirst=True)
    unresolved = dates.isna() & raw_dates.notna()
    if unresolved.any():
        dates.loc[unresolved] = pd.to_datetime(raw_dates.loc[unresolved], errors="coerce")
    dates = dates[dates.dt.year.eq(year)]
    return dates.dt.to_period("W-SAT").dt.start_time.value_counts()


def aggregate_notifications(disease: str, year: int) -> pd.DataFrame:
    spec = DISEASES[disease]
    with TemporaryDirectory() as temporary_directory:
        archive = Path(temporary_directory) / f"{disease}_{year}.zip"
        print(f"Downloading {disease}, {year} …")
        download(spec["sinan_url"].format(year=year, year2=f"{year % 100:02d}"), archive)
        if spec["format"] == "csv":
            # Keep the national dengue input memory-bounded: it is much larger
            # than the Zika and chikungunya extracts.
            counts = []
            for chunk in pd.read_csv(
                archive, compression="zip", usecols=["DT_NOTIFIC"], chunksize=250_000,
                dtype={"DT_NOTIFIC": "string"},
            ):
                counts.append(dates_to_week_counts(chunk["DT_NOTIFIC"], year))
            weeks = pd.concat(counts).groupby(level=0).sum()
        else:
            raw_dates = pd.read_json(archive, compression="zip")["DT_NOTIFIC"].astype("string")
            weeks = dates_to_week_counts(raw_dates, year)
    index = week_index(year)
    return pd.DataFrame({
        "date": index,
        "disease": disease,
        "sinan_notifications": weeks.reindex(index, fill_value=0).astype(int).to_numpy(),
    })


def fetch_google_trends() -> pd.DataFrame:
    terms = [spec["google_term"] for spec in DISEASES.values()]
    trends = TrendReq(hl="pt-BR", tz=0, timeout=(10, 45), retries=2, backoff_factor=0.5)
    trends.build_payload(terms, timeframe="2024-01-01 2025-12-31", geo="BR")
    data = trends.interest_over_time().reset_index()
    return data[["date", *terms]].melt("date", var_name="disease", value_name="google_trends")


def fetch_wikipedia() -> pd.DataFrame:
    frames = []
    for disease, spec in DISEASES.items():
        url = (
            "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
            f"pt.wikipedia/all-access/all-agents/{quote(spec['wiki_article'], safe='_')}/"
            "monthly/2023120100/2026010100"
        )
        request = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=60) as response:
            items = json.load(response)["items"]
        frames.append(pd.DataFrame({
            "date": pd.to_datetime([item["timestamp"][:8] for item in items], format="%Y%m%d"),
            "disease": disease,
            "wikipedia_pageviews": [item["views"] for item in items],
        }))
    return pd.concat(frames, ignore_index=True)


def main() -> None:
    notifications = pd.concat(
        [aggregate_notifications(disease, year) for disease in DISEASES for year in (2024, 2025)],
        ignore_index=True,
    )
    # The Sunday-starting week at the annual boundary is represented by days in
    # both extracts (for example, 2024-12-29). Sum those complementary partial
    # weeks into one disease-week before modeling.
    notifications = (
        notifications.groupby(["date", "disease"], as_index=False)["sinan_notifications"]
        .sum()
        .sort_values(["disease", "date"])
    )
    notifications.to_csv(HERE / "brazil_arbovirus_sinan_notifications_2024_2025_weekly.csv", index=False)

    trends = fetch_google_trends()
    trends.to_csv(HERE / "brazil_arbovirus_google_trends_pt_2024_2025_weekly.csv", index=False)
    wikipedia = fetch_wikipedia()
    wikipedia.to_csv(HERE / "brazil_arbovirus_wikipedia_pt_2023_2025_monthly.csv", index=False)

    combined = notifications.merge(trends, on=["date", "disease"], how="left")
    combined = pd.merge_asof(
        combined.sort_values(["date", "disease"]), wikipedia.sort_values(["date", "disease"]),
        on="date", by="disease", direction="backward"
    ).sort_values(["disease", "date"])
    if combined[["sinan_notifications", "google_trends", "wikipedia_pageviews"]].isna().any().any():
        raise ValueError("Missing outcome or attention signal after merging")
    combined["year"] = combined["date"].dt.year
    combined.to_csv(HERE / "brazil_arbovirus_notification_attention_2024_2025_weekly.csv", index=False)
    print("Saved weekly notification and attention data to", HERE)


if __name__ == "__main__":
    main()
