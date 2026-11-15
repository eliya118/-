"""A few fixed phrases for the fake adapter. Not a general parser."""

from __future__ import annotations

import re


def _clarify(reason: str) -> dict[str, object]:
    return {"status": "clarify", "reason": reason}


def match_fixed_phrase(text: str) -> dict[str, object] | None:
    raw = text.strip()
    if not raw:
        return None
    lowered = raw.lower()
    scrubbed = re.sub(r"ל-?child_\d+", " ", raw)
    scrubbed = re.sub(r"\bfor\s+child_\d+\b", " ", scrubbed, flags=re.IGNORECASE)
    if re.search(r"\bfor\s+[A-Za-z]", scrubbed):
        return _clarify("unknown")
    if re.search(r"ל[\u0590-\u05FF]", scrubbed):
        return _clarify("unknown")

    date_token: str | None = None
    if "אחרי החג" in raw or "after the holiday" in lowered or "after chag" in lowered:
        date_token = "after_chag"
    elif "ערב חג" in raw or "erev chag" in lowered:
        date_token = "erev_chag"
    elif "ערב שבת" in raw or "erev shabbat" in lowered:
        date_token = "erev_shabbat"
    elif "שבת" in raw or re.search(r"\bshabbat\b", lowered):
        date_token = "shabbat"
    elif "מחר" in raw or re.search(r"\btomorrow\b", lowered):
        date_token = "tomorrow"
    elif "יום ראשון" in raw or re.search(r"\bsunday\b", lowered):
        date_token = "sunday"
    if date_token is None:
        return None

    time_match = re.search(r"(\d{1,2}):(\d{2})", raw)
    all_day = "כל היום" in raw or "all day" in lowered
    children = re.findall(r"child_\d+", raw)
    if not children:
        return _clarify("child")
    if time_match is None and not all_day:
        return _clarify("time")

    title = raw
    for piece in (
        r"\bfor\s+child_\d+\b",
        r"ל-?child_\d+",
        r"child_\d+",
        r"\d{1,2}:\d{2}",
        r"\btomorrow\b",
        r"\bsunday\b",
        r"\bshabbat\b",
        r"\berev\b",
        r"\bchag\b",
        r"\bafter\b",
        r"\bthe\b",
        r"\bholiday\b",
        r"\bfor\b",
        r"\bat\b",
        r"\bon\b",
        r"בשעה",
        r"מחר",
        r"יום ראשון",
        r"ערב חג",
        r"ערב שבת",
        r"אחרי החג",
        r"שבת",
        r"כל היום",
        r"\ball day\b",
    ):
        title = re.sub(piece, " ", title, flags=re.IGNORECASE)
    title = re.sub(r"\s+", " ", title).strip(" -–")
    return {
        "status": "extract",
        "title": title,
        "child_tokens": children,
        "date_token": date_token,
        "time_hhmm": f"{int(time_match.group(1)):02d}:{time_match.group(2)}" if time_match else None,
        "all_day": all_day,
        "unknown_child": False,
    }
