# SISMID 2026: Statistics and Modeling with Novel Data Streams

Course environment for the SISMID 2026 module taught by **Mauricio Santillana** and
**Shihao Yang** (TA: **Candice Djorno**). Everything runs in an identical, browser-based
**GitHub Codespace**, so no local setup is required.

## Quick start (students)

1. Sign in to GitHub (a free account is fine).
2. Click the green **Code** button on this repo, choose the **Codespaces** tab, and
   click **Create codespace on main**. The environment builds automatically in about a
   minute.
3. When it opens, run the smoke test to confirm everything works:
   open `notebooks/00_smoke_test.ipynb` and run all cells, or in the terminal run:
   ```bash
   python scripts/smoke_test.py
   ```
   You should see library versions and "Environment OK".

That is all you need for Day 1. The exercises and data will appear in `notebooks/`
and `data/` as the course progresses.

## What is installed

This initial image is deliberately lightweight:

- **Python 3.12** with a small scientific stack (`numpy`, `pandas`, `matplotlib`,
  `scikit-learn`, `jupyterlab`, `requests`). See `requirements.txt`.
- **Node.js (LTS)**, so the AI coding agents can be installed with one command when we
  reach that part of the course.
- The VS Code Python and Jupyter extensions.

**No AI agent is preinstalled.** We install the agents together during the course so
you see how it is done and can reproduce it on your own machine. See
[`docs/agent-setup.md`](docs/agent-setup.md).

## Repository layout

```
.devcontainer/     Codespaces / dev container definition (the controlled environment)
requirements.txt   Python packages installed on container build
notebooks/         Course notebooks (starts with a smoke test)
data/              Datasets and cached snapshots (added during the course)
docs/              Guides, including agent setup
scripts/           Helper scripts (smoke test, agent installer)
```

## Fallback

If you cannot use Codespaces, you can run the notebooks in Google Colab or locally with
`pip install -r requirements.txt` on Python 3.12. Codespaces is the supported path.
