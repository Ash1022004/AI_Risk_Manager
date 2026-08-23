from __future__ import annotations

from app import store
from app.seeds import SEED_MERCHANTS
from ml.features import normalize_features


def main() -> None:
    created = []
    for item in SEED_MERCHANTS:
        merchant = store.create_merchant(
            {
                "name": item["name"],
                "category": item["category"],
                "source": item["source"],
                "features": normalize_features(item["features"]),
            }
        )
        created.append(merchant)
        print(f"Seeded {merchant['name']} ({merchant['id']}) via {store.backend_mode()}")
    print(f"Done. {len(created)} merchants stored.")


if __name__ == "__main__":
    main()
