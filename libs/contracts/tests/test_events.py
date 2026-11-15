import json
from pathlib import Path

from contracts.events import EventUpserted, parse_event

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "event_upserted.json"


def test_fixture_event_validates() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    event = parse_event(payload["type"], payload)
    assert isinstance(event, EventUpserted)
    assert event.generation == 1
    assert event.title == "dentist"
