from datetime import date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest
from kc_calendar.domain.age import age_band
from kc_calendar.domain.names import tokenize
from kc_calendar.domain.remind import compute_remind_at
from kc_calendar.domain.week import NotSundayError, require_sunday

from hebrewcal import week_start

JERUSALEM = ZoneInfo("Asia/Jerusalem")


def test_week_starts_on_sunday_and_rejects_other_days() -> None:
    wednesday = date(2026, 1, 7)
    sunday = date(2026, 1, 4)
    assert wednesday.weekday() == 2
    assert sunday.weekday() == 6
    assert week_start(wednesday) == sunday
    assert week_start(sunday) == sunday
    require_sunday(sunday)
    with pytest.raises(NotSundayError):
        require_sunday(wednesday)


def test_jerusalem_dst_sample_dates() -> None:
    zone = ZoneInfo("Asia/Jerusalem")
    assert datetime(2025, 3, 27, 12, tzinfo=zone).utcoffset() == timedelta(hours=2)
    assert datetime(2025, 3, 29, 12, tzinfo=zone).utcoffset() == timedelta(hours=3)
    assert datetime(2025, 10, 25, 12, tzinfo=zone).utcoffset() == timedelta(hours=3)
    assert datetime(2025, 10, 27, 12, tzinfo=zone).utcoffset() == timedelta(hours=2)


def test_longest_child_name_wins() -> None:
    short = UUID(int=1)
    long = UUID(int=2)
    text, tokens = tokenize("Noa Miriam dentist", [(short, "Noa"), (long, "Noa Miriam")])
    assert text == "child_2 dentist"
    assert tokens["child_2"] == long
    assert "Noa" not in text.split()[0]


def test_remind_at_defaults_and_past_is_null() -> None:
    now = datetime(2026, 1, 7, 9, tzinfo=JERUSALEM)
    starts = datetime(2026, 1, 7, 15, tzinfo=JERUSALEM)
    remind = compute_remind_at(starts, all_day=False, now=now, offset_minutes=None)
    assert remind == datetime(2026, 1, 7, 14, tzinfo=JERUSALEM)
    past = compute_remind_at(datetime(2026, 1, 7, 9, 30, tzinfo=JERUSALEM), False, now, None)
    assert past is None
    all_day = compute_remind_at(datetime(2026, 1, 8, 0, tzinfo=JERUSALEM), True, now, None)
    assert all_day == datetime(2026, 1, 8, 8, tzinfo=JERUSALEM)


def test_age_bands() -> None:
    today = date(2026, 6, 1)
    assert age_band(2024, 7, today) == "0-2"
    assert age_band(2021, 1, today) == "3-5"
    assert age_band(2018, 6, today) == "6-8"
    assert age_band(2015, 8, today) == "9-12"
    assert age_band(2012, 1, today) == "13-17"
