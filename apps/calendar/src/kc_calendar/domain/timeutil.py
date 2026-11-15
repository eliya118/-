import datetime as dt
from zoneinfo import ZoneInfo

JERUSALEM = ZoneInfo("Asia/Jerusalem")


def now_jerusalem() -> dt.datetime:
    return dt.datetime.now(JERUSALEM)


def jerusalem_today() -> dt.date:
    return now_jerusalem().date()


def as_jerusalem(moment: dt.datetime) -> dt.datetime:
    if moment.tzinfo is None:
        raise ValueError("time must include an offset")
    return moment.astimezone(JERUSALEM)


def civil_date(moment: dt.datetime) -> dt.date:
    return as_jerusalem(moment).date()
