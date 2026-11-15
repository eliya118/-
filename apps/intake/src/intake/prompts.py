INSTRUCTIONS = """You extract a calendar event from a parent's sentence.
The sentence may be Hebrew or English. Child names are already tokens like child_1.
Return JSON only. Do not invent a clock time.
If the sentence has no clock time and is not all-day, leave time_hhmm null.
date_token must be one of: tomorrow, sunday, shabbat, erev_shabbat, erev_chag, after_chag, or null.
If a person is named who is not one of the child tokens, set unknown_child true.
Do not compute a calendar date. Do not include the original names.
"""

EXTRACTION_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "title": {"type": ["string", "null"]},
        "child_tokens": {"type": "array", "items": {"type": "string"}},
        "date_token": {"type": ["string", "null"]},
        "time_hhmm": {"type": ["string", "null"]},
        "all_day": {"type": "boolean"},
        "unknown_child": {"type": "boolean"},
    },
    "required": ["title", "child_tokens", "date_token", "time_hhmm", "all_day", "unknown_child"],
}
