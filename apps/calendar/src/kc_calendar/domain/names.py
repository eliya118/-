"""Replace known child names with tokens before anything leaves calendar."""

from uuid import UUID


def tokenize(text: str, children: list[tuple[UUID, str]]) -> tuple[str, dict[str, UUID]]:
    """Longest display name first. Token numbers follow sorted child ids."""
    ordered_ids = sorted(children, key=lambda item: str(item[0]))
    token_of = {child_id: f"child_{index}" for index, (child_id, _name) in enumerate(ordered_ids, start=1)}
    replaced = text
    for child_id, name in sorted(children, key=lambda item: len(item[1]), reverse=True):
        cleaned = name.strip()
        if not cleaned:
            continue
        replaced = replaced.replace(cleaned, token_of[child_id])
    return replaced, {token: child_id for child_id, token in token_of.items()}
