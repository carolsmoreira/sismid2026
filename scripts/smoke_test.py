"""Minimal environment smoke test for SISMID 2026.

Run: python scripts/smoke_test.py
Confirms the core scientific stack imports and can do a trivial computation.
"""
import sys


def main() -> int:
    print(f"Python {sys.version.split()[0]}")
    import numpy as np
    import pandas as pd
    import matplotlib
    import sklearn
    import requests  # noqa: F401

    for mod in (np, pd, matplotlib, sklearn):
        print(f"{mod.__name__:12s} {mod.__version__}")

    # Trivial computation so we know numpy/pandas actually work.
    df = pd.DataFrame({"x": np.arange(5)})
    df["y"] = df["x"] ** 2
    assert df["y"].sum() == 30, "unexpected result"

    print("Environment OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
