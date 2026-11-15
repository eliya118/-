import datetime as dt
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest
from kc_calendar.google_sync import GoogleSyncError, event_payload, read_state, sign_state

FAMILY = UUID("11111111-1111-1111-1111-111111111111")
JERUSALEM = ZoneInfo("Asia/Jerusalem")


def test_state_round_trip() -> None:
    state = sign_state(FAMILY, "secret", now=1_700_000_000)
    assert read_state(state, "secret", now=1_700_000_100) == FAMILY


def test_state_rejects_a_tampered_value() -> None:
    state = sign_state(FAMILY, "secret", now=1_700_000_000)
    with pytest.raises(GoogleSyncError):
        read_state(state[:-1] + ("a" if state[-1] != "a" else "b"), "secret", now=1_700_000_100)


def test_timed_event_payload_uses_jerusalem() -> None:
    start = dt.datetime(2026, 11, 16, 16, 0, tzinfo=JERUSALEM)
    body = event_payload("dentist", start, None, False)
    assert body["summary"] == "dentist"
    assert body["start"] == {"dateTime": start.isoformat(), "timeZone": "Asia/Jerusalem"}
    end = body["end"]
    assert isinstance(end, dict)
    assert end["dateTime"] == (start + dt.timedelta(hours=1)).isoformat()


def test_all_day_payload_uses_dates() -> None:
    start = dt.datetime(2026, 11, 16, 0, 0, tzinfo=JERUSALEM)
    body = event_payload("trip", start, None, True)
    assert body["start"] == {"date": "2026-11-16"}
    assert body["end"] == {"date": "2026-11-17"}
