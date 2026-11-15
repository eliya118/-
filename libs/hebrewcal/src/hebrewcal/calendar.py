"""Hebrew dates and Israel holidays for one civil day. Computed, never stored."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Literal
from zoneinfo import ZoneInfo

from hdate import HDateInfo, HebrewDate, Location, Zmanim
from hdate.hebrew_date import Months
from hdate.holidays import HolidayTypes
from hdate.translations import TRANSLATIONS

JERUSALEM_TZ = ZoneInfo("Asia/Jerusalem")
LOCATION = Location(
    name="Jerusalem",
    latitude=31.778,
    longitude=35.235,
    timezone="Asia/Jerusalem",
    diaspora=False,
)
CANDLE_LIGHTING_MINUTES = 40

HolidayKind = Literal["yom_tov", "chol_hamoed", "fast", "rosh_chodesh", "memorial", "other"]
DayContext = Literal["ordinary", "shabbat", "yom_tov", "chol_hamoed"]

_KIND: dict[HolidayTypes, HolidayKind] = {
    HolidayTypes.YOM_TOV: "yom_tov",
    HolidayTypes.HOL_HAMOED: "chol_hamoed",
    HolidayTypes.FAST_DAY: "fast",
    HolidayTypes.ROSH_CHODESH: "rosh_chodesh",
    HolidayTypes.MEMORIAL_DAY: "memorial",
}


@dataclass(frozen=True)
class HebrewParts:
    year: int
    month: str
    day: int
    display_he: str
    display_en: str


@dataclass(frozen=True)
class HolidayMark:
    kind: HolidayKind
    name_he: str
    name_en: str


@dataclass(frozen=True)
class DayInfo:
    civil_date: dt.date
    hebrew: HebrewParts
    shabbat: bool
    holidays: list[HolidayMark]
    candle_lighting: dt.datetime | None
    havdalah: dt.datetime | None


def _translated(table: str, key: str, lang: str) -> str:
    return TRANSLATIONS[lang].get(table, {}).get(key.lower(), key)


def hebrew_parts(civil: dt.date) -> HebrewParts:
    from hdate.gematria import hebrew_number

    hebrew = HebrewDate.from_gdate(civil)
    month_key = hebrew.month.name.lower()
    month_he = _translated("Months", month_key, "he")
    month_en = _translated("Months", month_key, "en")
    return HebrewParts(
        year=hebrew.year,
        month=month_key,
        day=hebrew.day,
        display_he=f"{hebrew_number(hebrew.day)} {month_he} {hebrew_number(hebrew.year)}",
        display_en=f"{hebrew.day} {month_en} {hebrew.year}",
    )


def _on_civil_date(instant: dt.datetime | None, civil: dt.date) -> dt.datetime | None:
    if instant is None:
        return None
    local = instant.astimezone(JERUSALEM_TZ)
    if local.date() != civil:
        return None
    return local


def describe_day(civil: dt.date) -> DayInfo:
    info = HDateInfo(civil, diaspora=False)
    holidays = [
        HolidayMark(
            kind=_KIND.get(holiday.type, "other"),
            name_he=_translated("Holiday", holiday.name, "he"),
            name_en=_translated("Holiday", holiday.name, "en"),
        )
        for holiday in info.holidays
    ]
    zmanim = Zmanim(civil, LOCATION, candle_lighting_offset=CANDLE_LIGHTING_MINUTES)
    return DayInfo(
        civil_date=civil,
        hebrew=hebrew_parts(civil),
        shabbat=civil.weekday() == 5,
        holidays=holidays,
        candle_lighting=_on_civil_date(zmanim.candle_lighting, civil),
        havdalah=_on_civil_date(zmanim.havdalah, civil),
    )


def is_sunday(civil: dt.date) -> bool:
    return civil.weekday() == 6


def week_start(civil: dt.date) -> dt.date:
    """Sunday of the week that contains `civil`, or `civil` when it is Sunday."""
    days_since_sunday = (civil.weekday() + 1) % 7
    return civil - dt.timedelta(days=days_since_sunday)


def describe_week(sunday: dt.date) -> list[DayInfo]:
    if not is_sunday(sunday):
        raise ValueError("week start must be a Sunday")
    return [describe_day(sunday + dt.timedelta(days=offset)) for offset in range(7)]


def day_context(info: DayInfo) -> DayContext:
    kinds = {holiday.kind for holiday in info.holidays}
    if "yom_tov" in kinds:
        return "yom_tov"
    if "chol_hamoed" in kinds:
        return "chol_hamoed"
    if info.shabbat:
        return "shabbat"
    return "ordinary"


def day_label(info: DayInfo, locale: str) -> str:
    for holiday in info.holidays:
        if holiday.kind in {"yom_tov", "chol_hamoed"}:
            return holiday.name_he if locale == "he" else holiday.name_en
    if info.shabbat:
        return "שבת" if locale == "he" else "Shabbat"
    return ""


def festival_blocks(hebrew_year: int) -> list[tuple[str, dt.date, dt.date]]:
    """Israel festival blocks as (key, first civil day, last civil day)."""

    def span(month: Months, start_day: int, end_day: int, key: str) -> tuple[str, dt.date, dt.date]:
        start = HebrewDate(hebrew_year, month, start_day).to_gdate()
        end = HebrewDate(hebrew_year, month, end_day).to_gdate()
        return key, start, end

    return [
        span(Months.TISHREI, 1, 2, "rosh_hashanah"),
        span(Months.TISHREI, 10, 10, "yom_kippur"),
        span(Months.TISHREI, 15, 22, "sukkot"),
        span(Months.NISAN, 15, 21, "pesach"),
        span(Months.SIVAN, 6, 6, "shavuot"),
    ]
