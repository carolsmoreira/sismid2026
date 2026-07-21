# Wikipedia and Brazil dengue comparison

This folder contains the Wikipedia pageview work and the national Brazil dengue comparison produced for the course workspace.

## Main outputs

| File | Contents |
| --- | --- |
| `dengue_pageviews_en_es_pt.csv` | Monthly dengue article pageviews for English, Spanish, and Portuguese Wikipedia. |
| `brazil_sinan_dengue_2024_weekly.csv` | Brazil-wide 2024 SINAN dengue notifications, grouped by symptom-onset week. |
| `brazil_sinan_dengue_2025_weekly.csv` | The corresponding 2025 weekly series. |
| `brazil_google_trends_dengue_2024_weekly.csv` / `...2025...` | Weekly Brazil Google Trends interest for `dengue`; both years come from one two-year request and share a common scale. |
| `brazil_wikipedia_pt_2023_2025_monthly.csv` | Portuguese Wikipedia dengue pageviews used as a monthly Brazil-oriented attention proxy. |
| `brazil_dengue_sinan_wikipedia_google_trends_2024.png` | 2024 cases, Google Trends, and Wikipedia comparison. |
| `brazil_dengue_2025_mlr_predictions.png` | 2025 prediction-versus-observation plot. |
| `brazil_dengue_2025_mlr_predictions.csv` | Weekly predictions and observed 2025 notifications. |
| `brazil_dengue_2025_mlr_metrics.csv` | MAE, RMSE, correlation, and predicted total for each model. |

## Code

- `fetch_dengue_pageviews.py` fetches English, Spanish, and Portuguese monthly Wikipedia pageviews and saves the three-language CSV/plot.
- `build_brazil_dengue_data.py` downloads the 2024 and 2025 national SINAN dengue line lists temporarily, aggregates them weekly, fetches a common-scale two-year Google Trends series, fetches Portuguese Wikipedia pageviews, and writes the national inputs plus the 2024 comparison plot.
- `model_brazil_2025_nowcast.py` trains and evaluates the 2025 Brazil models from those saved inputs.

Run from the repository root:

```bash
python wikipedia/build_brazil_dengue_data.py
python wikipedia/model_brazil_2025_nowcast.py
```

The build script downloads roughly 220 MB of compressed SINAN source data, processes it in chunks, and removes its temporary copies automatically.

## Sources and definitions

SINAN data are from the Brazilian Ministry of Health's Open Data SUS dengue line lists: [2024](https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SINAN/Dengue/csv/DENGBR24.csv.zip) and [2025](https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SINAN/Dengue/csv/DENGBR25.csv.zip). Each weekly count is the number of records with a symptom-onset date in that Sunday--Saturday week. These are notification records, not a final confirmed-case count.

Google Trends is a normalized search-interest index for the search term `dengue`, geography `BR`. It is fetched for 2024--2025 in one request because separate Google Trends queries are independently normalized and cannot be compared directly.

Portuguese Wikipedia data are monthly pageviews for the article `Dengue` on `pt.wikipedia`. They are not Rio-specific; they are used as a Brazil-oriented language-level attention proxy. The monthly value is carried across the weeks within its month.

## Models

Both models predict `log1p` weekly SINAN notifications using same-week Google Trends interest and Portuguese Wikipedia pageviews.

- **Fixed 2024 MLR:** fit on 2024 only, then applied unchanged to 2025. This is the strict train-2024/test-2025 comparison.
- **Dynamic 52-week MLR:** refit every week using the preceding 52 observed weeks. It can use prior 2025 notifications and is therefore a rolling nowcast, not a pure 2024-trained forecast.

The final week beginning 2025-12-28 is excluded from model scoring because it continues into 2026 while the 2025 SINAN line list contains only its 2025 days.

These are retrospective same-period nowcasts, not advance forecasts: Google Trends is contemporaneous, and a monthly Wikipedia total is only fully known after the month ends.
