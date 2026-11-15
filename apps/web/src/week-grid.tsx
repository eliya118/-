import type { Locale } from "./i18n";
import { translate } from "./i18n";
import type { CalEvent, Day } from "./api";
import { clock } from "./week";

export function WeekGrid({
  days,
  events,
  locale,
  childNames,
}: {
  days: Day[];
  events: CalEvent[];
  locale: Locale;
  childNames: Record<string, string>;
}) {
  const t = (key: Parameters<typeof translate>[1]) => translate(locale, key);
  return (
    <div className="week">
      {days.map((day) => {
        const names = day.holidays.map((holiday) => (locale === "he" ? holiday.name_he : holiday.name_en));
        const hebrew = locale === "he" ? day.hebrew.display_he : day.hebrew.display_en;
        const dayEvents = events.filter((event) => event.civil_date === day.civil_date);
        return (
          <section
            key={day.civil_date}
            className={day.shabbat ? "day shabbat" : "day"}
            data-civil={day.civil_date}
          >
            <header>
              <div className="civil">{day.civil_date}</div>
              <div className="hebrew">{hebrew}</div>
            </header>
            {day.shabbat ? <p className="mark">{t("shabbat")}</p> : null}
            {names.map((name) => (
              <p key={name} className="mark">
                {name}
              </p>
            ))}
            {day.candle_lighting ? (
              <p className="zman">
                {t("candle")} {clock(day.candle_lighting)}
              </p>
            ) : null}
            {day.havdalah ? (
              <p className="zman">
                {t("havdalah")} {clock(day.havdalah)}
              </p>
            ) : null}
            <ul>
              {dayEvents.length === 0 ? <li className="empty">{t("noEvents")}</li> : null}
              {dayEvents.map((event) => (
                <li key={event.id}>
                  <strong>{event.title}</strong>
                  <span>
                    {event.all_day ? t("allDay") : clock(event.starts_at)}
                    {" · "}
                    {event.child_ids.map((id) => childNames[id] ?? id).join(", ")}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
