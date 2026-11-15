from ideas.catalog_loader import load_catalog, pick_items


def test_seed_answers_without_a_key() -> None:
    catalog = load_catalog()
    items = pick_items(catalog, "activity", "6-8", "he", "activity", "shabbat")
    assert items
    assert any("שבת" in item["text"] for item in items)
    meals = pick_items(catalog, "meal", "general", "en", "breakfast", "ordinary")
    assert meals
    assert meals[0]["text"]
