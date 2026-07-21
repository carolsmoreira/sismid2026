# Rio de Janeiro dengue Trends outputs

- `01_scrape_your_topic.ipynb`: completed notebook with the fetching, topic, stability, and save steps.
- `my_topic_search.csv`: live Google Trends terms for Rio de Janeiro, past five years.
- `rio_dengue_trends_2024.png`: individual query terms in 2024.
- `rio_dengue_trends_5y.png`: individual query terms over the past five years.
- `rio_dengue_terms_vs_topic_2024.png`: individual terms versus the combined query and Google Trends dengue topic.
- `rio_dengue_terms_vs_topic_5y.png`: the same term-versus-topic comparison over the past five years.
- `rio_dengue_terms_vs_topic_5y.csv`: weekly values used for the five-year term-versus-topic plot.
- `rio_dengue_trends_vs_sinan_2024_weekly.csv`: 2024 weekly Trends and SINAN notification comparison table.
- `rio_dengue_trends_vs_sinan_2024.png`: 2024 Trends versus SINAN notification comparison plot.
- `rio_dengue_sinan_2025_weekly.csv`: 2025 Rio-resident dengue notifications, grouped by symptom-onset week.
- `rio_dengue_2025_nowcast_predictions.csv`: 2025 actual notifications and predictions from a model fit on 2024 data.
- `rio_dengue_2025_nowcast.png`: actual-versus-predicted 2025 nowcast plot.
- `rio_dengue_2025_mlr_dynamic.png`: fixed versus dynamic multiple-linear-regression nowcasts for 2025.
- `rio_dengue_2025_mlr_dynamic_predictions.csv`: weekly actual values plus fixed and dynamic model predictions.
- `rio_dengue_2025_mlr_dynamic_metrics.csv`: 2025 evaluation metrics for both multiple-linear-regression models.
- `model_2025_nowcast.py`: reproducible script for the fixed and dynamic multiple-linear-regression comparison.

The SINAN series represents notified dengue cases among Rio de Janeiro residents, grouped by symptom-onset week.

The 2025 models are multiple linear regressions fit on log weekly notifications.
They use same-week Google Trends values for `dengue`, `fever`, and `sintomas de dengue`,
plus Portuguese Wikipedia `Dengue` monthly pageviews carried across the weeks in
each month. The Wikipedia series is Brazil-oriented rather than Rio-specific. These
are nowcasts, not advance forecasts, because the search and pageview signals are
contemporaneous.

The dynamic multiple-linear-regression model refits each week on the most recent
52 observed weeks, using only observations available before that prediction week.
The final, partial week beginning 2025-12-28 is excluded from scoring.

## 2025 model check

| Model | Training scheme | MAE | RMSE | Pearson correlation |
|---|---|---:|---:|---:|
| Fixed multiple linear regression | 2024 only | 404 | 454 | 0.78 |
| Dynamic multiple linear regression | preceding 52 observed weeks | 186 | 285 | 0.86 |

Both models use same-week Google Trends values and monthly Portuguese Wikipedia
pageviews; they are nowcasts rather than advance forecasts. The dynamic model may
use prior 2025 notifications as they become available, whereas the fixed model does
not.

## Comparison with the previous Google-Trends-only models

The comparison below evaluates both versions on the same 52 complete weeks of
2025. Adding Portuguese Wikipedia `Dengue` pageviews substantially improved the
dynamic model: MAE fell from 226 to 186 (18%), RMSE fell from 360 to 285 (21%),
and correlation rose from 0.75 to 0.86. The fixed 2024-only model followed the
weekly pattern more closely (correlation 0.68 to 0.78), but its MAE increased
slightly (392 to 404). This suggests the Wikipedia signal is most useful in the
rolling nowcast, which can adapt as the attention--case relationship changes.

See `rio_dengue_2025_nowcast_version_comparison.png` for the weekly trajectories
and `rio_dengue_2025_nowcast_version_comparison_metrics.csv` for the matched-week
metrics. Recreate them with:

```bash
python rj_trends/compare_nowcast_versions.py
```

Recreate the dynamic-model outputs with:

```bash
python model_2025_nowcast.py
```
