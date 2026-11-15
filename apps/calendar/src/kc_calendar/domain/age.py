import datetime as dt

BANDS: tuple[tuple[int, int, str], ...] = (
    (0, 2, "0-2"),
    (3, 5, "3-5"),
    (6, 8, "6-8"),
    (9, 12, "9-12"),
    (13, 17, "13-17"),
)


def age_years(birth_year: int, birth_month: int, today: dt.date) -> int:
    age = today.year - birth_year
    if today.month < birth_month:
        age -= 1
    return age


def age_band(birth_year: int, birth_month: int, today: dt.date) -> str:
    age = age_years(birth_year, birth_month, today)
    if age < 0:
        return "0-2"
    for low, high, label in BANDS:
        if low <= age <= high:
            return label
    return "13-17"
