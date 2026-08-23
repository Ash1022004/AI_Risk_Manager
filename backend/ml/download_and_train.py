from __future__ import annotations

import os
import zipfile
from pathlib import Path

from app.config import get_settings
from ml.synthetic import generate_synthetic_merchants
from ml.train import train_model

ROOT = Path(__file__).resolve().parent.parent
IEEE_DIR = ROOT / "data" / "ieee-cis"


def _try_kaggle_download() -> bool:
    settings = get_settings()
    if not settings.kaggle_api_token:
        print("KAGGLE_API_TOKEN missing — skipping IEEE-CIS download.")
        return False
    os.environ.setdefault("KAGGLE_API_TOKEN", settings.kaggle_api_token)
    IEEE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi

        api = KaggleApi()
        api.authenticate()
        print("Downloading ieee-fraud-detection from Kaggle...")
        api.competition_download_files("ieee-fraud-detection", path=str(IEEE_DIR), quiet=False)
        for zip_path in IEEE_DIR.glob("*.zip"):
            with zipfile.ZipFile(zip_path) as archive:
                archive.extractall(IEEE_DIR)
        return (IEEE_DIR / "train_transaction.csv").exists()
    except Exception as exc:
        print(f"Kaggle download failed ({exc}). Using synthetic merchants instead.")
        print("If this is a 403, accept the competition rules at:")
        print("https://www.kaggle.com/competitions/ieee-fraud-detection/rules")
        return False


def main() -> None:
    source = "synthetic"
    frame = None
    if (IEEE_DIR / "train_transaction.csv").exists() or _try_kaggle_download():
        try:
            from ml.reshape import reshape_ieee

            print("Reshaping IEEE-CIS into merchant signals...")
            frame = reshape_ieee(IEEE_DIR)
            source = "ieee-cis"
        except Exception as exc:
            print(f"IEEE reshape failed ({exc}). Falling back to synthetic data.")

    if frame is None:
        print("Generating synthetic merchant-risk dataset...")
        frame = generate_synthetic_merchants()

    meta = train_model(frame, source=source)
    print(f"Trained LightGBM on {meta['n_rows']} rows from {meta['source']}. val AUC={meta['auc']:.3f}")


if __name__ == "__main__":
    main()
