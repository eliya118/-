"""Locked Israel-schedule examples. A library upgrade must not flip these to the diaspora."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from hebrewcal import describe_day, describe_week, resolve_relative

JERUSALEM = ZoneInfo("Asia/Jerusalem")


def at(day: str, hour: int = 10) -> datetime:
    year, month, day_num = (int(part) for part in day.split("-"))
    return datetime(year, month, day_num, hour, tzinfo=JERUSALEM)


def test_week_has_seven_hebrew_dates() -> None:
    days = describe_week(date(2025, 6, 1))
    assert len(days) == 7
    assert [day.civil_date.isoformat() for day in days][0] == "2025-06-01"
    assert days[-1].civil_date.isoformat() == "2025-06-07"
    stamps = [(day.hebrew.year, day.hebrew.month, day.hebrew.day) for day in days]
    assert len(set(stamps)) == 7
    assert all(day.hebrew.display_he and day.hebrew.display_en for day in days)


def test_shavuot_is_one_day_in_israel_and_after_chag_is_7_sivan() -> None:
    shavuot = describe_day(date(2025, 6, 2))
    assert any(holiday.kind == "yom_tov" and holiday.name_en == "Shavuot" for holiday in shavuot.holidays)
    assert shavuot.hebrew.month == "sivan"
    assert shavuot.hebrew.day == 6
    day_after = describe_day(date(2025, 6, 3))
    assert not any(holiday.name_en == "Shavuot" for holiday in day_after.holidays)
    assert day_after.hebrew.day == 7
    resolved = resolve_relative("after_chag", at("2025-06-02"))
    assert resolved == date(2025, 6, 3)
    assert resolve_relative("אחרי החג", at("2025-06-02")) == date(2025, 6, 3)


def test_rosh_hashanah_is_two_civil_days() -> None:
    first = describe_day(date(2024, 10, 3))
    second = describe_day(date(2024, 10, 4))
    third = describe_day(date(2024, 10, 5))
    assert any(holiday.kind == "yom_tov" and "Rosh Hashana" in holiday.name_en for holiday in first.holidays)
    assert any(holiday.kind == "yom_tov" and "Rosh Hashana" in holiday.name_en for holiday in second.holidays)
    assert not any(holiday.kind == "yom_tov" for holiday in third.holidays)
    assert resolve_relative("after_chag", at("2024-10-03")) == date(2024, 10, 5)


def test_16_nisan_is_chol_hamoed_not_yom_tov() -> None:
    day = describe_day(date(2025, 4, 14))
    assert day.hebrew.month == "nisan"
    assert day.hebrew.day == 16
    assert any(holiday.kind == "chol_hamoed" for holiday in day.holidays)
    assert not any(holiday.kind == "yom_tov" for holiday in day.holidays)
    # Pesach block ends 21 Nisan (2025-04-19); the next civil date is 22 Nisan.
    assert resolve_relative("after_chag", at("2025-04-14")) == date(2025, 4, 20)


def test_friday_has_candle_lighting_and_plain_wednesday_has_neither() -> None:
    friday = describe_day(date(2026, 1, 9))
    assert friday.civil_date.weekday() == 4
    assert friday.candle_lighting is not None
    assert friday.havdalah is None
    wednesday = describe_day(date(2026, 1, 7))
    assert wednesday.civil_date.weekday() == 2
    assert wednesday.candle_lighting is None
    assert wednesday.havdalah is None


def test_shabbat_and_sunday_follow_the_same_ahead_rule() -> None:
    # Sunday 1 June 2025, mid-morning: this Sunday's midnight is past, Saturday is ahead.
    now = at("2025-06-01")
    assert resolve_relative("sunday", now) == date(2025, 6, 8)
    assert resolve_relative("שבת", now) == date(2025, 6, 7)
    assert resolve_relative("erev_shabbat", now) == date(2025, 6, 6)
    # Saturday itself: that Saturday is no longer ahead.
    saturday = at("2025-06-07")
    assert resolve_relative("shabbat", saturday) == date(2025, 6, 14)


def test_tomorrow_and_erev_chag() -> None:
    now = at("2025-06-01")
    assert resolve_relative("tomorrow", now) == date(2025, 6, 2)
    assert resolve_relative("מחר", now) == date(2025, 6, 2)
    # Candle-lighting for Shavuot is still that evening.
    assert resolve_relative("erev_chag", now) == date(2025, 6, 1)
    assert resolve_relative("ערב חג", now) == date(2025, 6, 1)
    after_lighting = at("2025-06-01", hour=21)
    # Next festival eve after Shavuot 5785 is Rosh Hashanah 5786.
    assert resolve_relative("ערב חג", after_lighting) == date(2025, 9, 22)


def test_sukkot_after_chag_is_23_tishrei() -> None:
    # Inside the Israel Sukkot block (15–22 Tishrei), not merely after the first day.
    assert resolve_relative("אחרי החג", at("2024-10-20")) == date(2024, 10, 25)
    day = describe_day(date(2024, 10, 25))
    assert day.hebrew.month == "tishrei"
    assert day.hebrew.day == 23


def test_week_containing_a_wednesday_starts_on_sunday() -> None:
    from hebrewcal import week_start

    assert week_start(date(2026, 1, 7)) == date(2026, 1, 4)
    assert week_start(date(2026, 1, 4)) == date(2026, 1, 4)
    assert date(2026, 1, 4).weekday() == 6
