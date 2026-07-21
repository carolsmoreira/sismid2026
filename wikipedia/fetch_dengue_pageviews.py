"""Fetch monthly Dengue Wikipedia pageviews and save a merged CSV and plot."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

import matplotlib.pyplot as plt
import pandas as pd


USER_AGENT = "SISMID2026-wikipedia-pageviews/1.0 (course materials)"
OUTPUT_DIR = Path(__file__).resolve().parent
CACHE_PATH = OUTPUT_DIR.parent / "day2-0900-data-beyond-google-trends" / "data" / "wikipedia_dengue_pageviews_cached.csv"


def wiki_fetch(article: str, wiki: str, start: str = "2016010100", end: str = "2025120100") -> pd.DataFrame:
    """Return monthly pageviews for one article as columns ``date`` and ``views``."""
    url = (
        "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
        f"{wiki}/all-access/all-agents/{quote(article, safe='_')}/monthly/{start}/{end}"
    )
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=30) as response:
        items = json.load(response)["items"]
    return pd.DataFrame(
        {"date": pd.to_datetime([item["timestamp"][:8] for item in items], format="%Y%m%d"),
         "views": [item["views"] for item in items]}
    )


def load_cache() -> pd.DataFrame:
    """Read the supplied merged dengue pageview snapshot."""
    return pd.read_csv(CACHE_PATH, parse_dates=["date"])


def get_dengue_wiki() -> pd.DataFrame:
    """Fetch English, Spanish, and Portuguese dengue views; fall back to cache on failure."""
    try:
        series = [
            wiki_fetch("Dengue_fever", "en.wikipedia").rename(columns={"views": "dengue_en"}),
            wiki_fetch("Dengue", "es.wikipedia").rename(columns={"views": "dengue_es"}),
            wiki_fetch("Dengue", "pt.wikipedia").rename(columns={"views": "dengue_pt"}),
        ]
        return series[0].merge(series[1], on="date", validate="one_to_one").merge(
            series[2], on="date", validate="one_to_one"
        )
    except Exception as error:
        print(f"Live Wikimedia request failed; using cache ({type(error).__name__}: {error})")
        return load_cache()


def save_outputs() -> pd.DataFrame:
    """Save the merged CSV and a three-language line plot in ``wikipedia/``."""
    data = get_dengue_wiki().sort_values("date")
    data.to_csv(OUTPUT_DIR / "dengue_pageviews_en_es_pt.csv", index=False)

    ax = data.plot(x="date", y=["dengue_en", "dengue_es", "dengue_pt"], figsize=(10, 4))
    ax.set(title="Wikipedia pageviews: Dengue by language", xlabel="Date", ylabel="Monthly views")
    ax.figure.tight_layout()
    ax.figure.savefig(OUTPUT_DIR / "dengue_pageviews_en_es_pt.png", dpi=150)
    plt.close(ax.figure)
    return data


if __name__ == "__main__":
    saved = save_outputs()
    print(f"Saved {len(saved)} monthly observations to {OUTPUT_DIR}")
