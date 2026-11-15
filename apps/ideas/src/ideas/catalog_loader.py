import json
from pathlib import Path
from typing import Any

_CATALOG = Path(__file__).resolve().parent / "catalog" / "seed.json"


def load_catalog() -> dict[str, Any]:
    loaded = json.loads(_CATALOG.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise RuntimeError("seed catalog is not an object")
    return loaded


def pick_items(
    catalog: dict[str, Any],
    kind: str,
    age_band: str,
    locale: str,
    slot: str,
    day_context: str,
) -> list[dict[str, str]]:
    pool = catalog["activities"] if kind == "activity" else catalog["meals"]
    bands = [age_band, "general"] if age_band != "general" else ["general"]
    contexts = [day_context, "ordinary"] if day_context != "ordinary" else ["ordinary"]
    chosen: list[dict[str, str]] = []
    seen: set[str] = set()
    for band in bands:
        for context in contexts:
            for item in pool:
                if item.get("locale") != locale:
                    continue
                if item.get("age_band") not in {band, "general"} and item.get("age_band") != band:
                    continue
                if item.get("age_band") != band:
                    continue
                if item.get("day_context") != context:
                    continue
                if kind == "meal" and item.get("slot") != slot:
                    continue
                if item["id"] in seen:
                    continue
                seen.add(item["id"])
                chosen.append({"id": item["id"], "text": item["text"]})
                if len(chosen) == 3:
                    return chosen
    return chosen
