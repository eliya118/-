import datetime as dt

from hebrewcal import describe_week, is_sunday


class NotSundayError(ValueError):
    pass


def require_sunday(sunday: dt.date) -> None:
    if not is_sunday(sunday):
        raise NotSundayError("that date is not a Sunday in Asia/Jerusalem")


def week_days(sunday: dt.date) -> list[object]:
    require_sunday(sunday)
    return list(describe_week(sunday))
