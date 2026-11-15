import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useSearchParams } from "react-router";
import { api, type CalEvent, type Draft, type Family, type Preview, type Week } from "../api";
import type { Locale } from "../i18n";
import { translate } from "../i18n";
import { WeekGrid } from "../week-grid";
import { addDays, jerusalemToday, sundayOnOrBefore } from "../week";

export function WeekPage({ locale, family }: { locale: Locale; family: Family }) {
  const t = (key: Parameters<typeof translate>[1]) => translate(locale, key);
  const [sunday, setSunday] = useState(() => sundayOnOrBefore(jerusalemToday()));
  const week = useQuery({
    queryKey: ["week", sunday],
    queryFn: () => api<Week>(`/api/weeks/${sunday}`),
  });
  const client = useQueryClient();
  const googleStatus = useQuery({
    queryKey: ["google"],
    queryFn: () => api<{ configured: boolean; connected: boolean }>("/api/google/status"),
  });
  const cancel = useMutation({
    mutationFn: (eventId: string) => api(`/api/events/${eventId}`, { method: "DELETE" }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["week"] }),
  });
  const names = useMemo(
    () => Object.fromEntries(family.children.map((child) => [child.id, child.display_name])),
    [family.children],
  );
  return (
    <>
      <div className="row">
        <button className="quiet" type="button" onClick={() => setSunday(addDays(sunday, -7))}>
          {t("prevWeek")}
        </button>
        <button className="quiet" type="button" onClick={() => setSunday(addDays(sunday, 7))}>
          {t("nextWeek")}
        </button>
      </div>
      <GoogleCalendar locale={locale} />
      <Composer locale={locale} family={family} sunday={sunday} />
      {week.isLoading ? <p>{t("loading")}</p> : null}
      {week.data ? (
        <WeekGrid
          days={week.data.days}
          events={week.data.events}
          locale={locale}
          childNames={names}
          onCancel={(eventId) => {
            if (window.confirm(t("cancelConfirm"))) cancel.mutate(eventId);
          }}
          googleHref={googleStatus.data?.connected ? undefined : googleTemplate}
        />
      ) : null}
    </>
  );
}

function Composer({ locale, family, sunday }: { locale: Locale; family: Family; sunday: string }) {
  const t = (key: Parameters<typeof translate>[1]) => translate(locale, key);
  const client = useQueryClient();
  const [text, setText] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState("");
  const [manual, setManual] = useState(false);
  const [title, setTitle] = useState("");
  const [date, setDate] = useState(sunday);
  const [time, setTime] = useState("16:00");
  const [allDay, setAllDay] = useState(false);
  const [childId, setChildId] = useState(family.children[0]?.id ?? "");
  const [offset, setOffset] = useState(60);

  const refresh = () => client.invalidateQueries({ queryKey: ["week"] });

  const previewMutation = useMutation({
    mutationFn: () =>
      api<Preview>("/api/intake/preview", {
        method: "POST",
        body: JSON.stringify({ text, locale }),
      }),
    onSuccess: (result) => {
      setError("");
      setPreview(result);
    },
    onError: () => {
      setPreview(null);
      setError(t("parseDown"));
      setManual(true);
    },
  });

  const confirm = useMutation({
    mutationFn: (draft: Draft) =>
      api("/api/intake/confirm", {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify({ ...draft, locale }),
      }),
    onSuccess: () => {
      setPreview(null);
      setText("");
      void refresh();
    },
  });

  const createManual = useMutation({
    mutationFn: () => {
      const iso = toJerusalemIso(date, allDay ? "00:00" : time);
      return api("/api/events", {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify({
          title,
          starts_at: iso,
          ends_at: null,
          all_day: allDay,
          locale,
          child_ids: [childId],
          remind_offset_minutes: offset,
        }),
      });
    },
    onSuccess: () => {
      setTitle("");
      setManual(false);
      void refresh();
    },
  });

  return (
    <section className="panel">
      <form
        className="row"
        onSubmit={(event) => {
          event.preventDefault();
          previewMutation.mutate();
        }}
      >
        <label>
          {t("addSentence")}
          <input
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder={t("sentencePlaceholder")}
            size={48}
          />
        </label>
        <button type="submit">{t("preview")}</button>
        <button className="quiet" type="button" onClick={() => setManual((open) => !open)}>
          {t("manual")}
        </button>
      </form>
      {error ? <p className="error">{error}</p> : null}
      {preview?.status === "needs_clarification" ? <p>{preview.questions.join(" ")}</p> : null}
      {preview?.status === "ready" && preview.draft ? (
        <div className="row">
          <p>
            {preview.draft.title} · {preview.draft.starts_at}
          </p>
          <button type="button" onClick={() => confirm.mutate(preview.draft as Draft)}>
            {t("confirm")}
          </button>
        </div>
      ) : null}
      {manual ? (
        <form
          className="row"
          onSubmit={(event) => {
            event.preventDefault();
            createManual.mutate();
          }}
        >
          <label>
            {t("title")}
            <input value={title} onChange={(event) => setTitle(event.target.value)} required />
          </label>
          <label>
            {t("date")}
            <input type="date" value={date} onChange={(event) => setDate(event.target.value)} required />
          </label>
          <label>
            {t("time")}
            <input type="time" value={time} onChange={(event) => setTime(event.target.value)} disabled={allDay} />
          </label>
          <label>
            {t("whichChild")}
            <select value={childId} onChange={(event) => setChildId(event.target.value)}>
              {family.children.map((child) => (
                <option key={child.id} value={child.id}>
                  {child.display_name}
                </option>
              ))}
            </select>
          </label>
          <label>
            {t("remindOffset")}
            <input
              type="number"
              min={0}
              max={10080}
              value={offset}
              onChange={(event) => setOffset(Number(event.target.value))}
            />
          </label>
          <label>
            {t("allDay")}
            <input type="checkbox" checked={allDay} onChange={(event) => setAllDay(event.target.checked)} />
          </label>
          <button type="submit">{t("save")}</button>
        </form>
      ) : null}
    </section>
  );
}

function GoogleCalendar({ locale }: { locale: Locale }) {
  const t = (key: Parameters<typeof translate>[1]) => translate(locale, key);
  const [params] = useSearchParams();
  const client = useQueryClient();
  const status = useQuery({
    queryKey: ["google"],
    queryFn: () => api<{ configured: boolean; connected: boolean }>("/api/google/status"),
  });
  const disconnect = useMutation({
    mutationFn: () => api("/api/google", { method: "DELETE" }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["google"] }),
  });
  if (!status.data) return null;
  return (
    <section className="panel">
      {params.get("google") === "error" ? <p className="error">{t("googleError")}</p> : null}
      {status.data.connected ? (
        <div className="row">
          <p>{t("googleConnected")}</p>
          <button className="quiet" type="button" onClick={() => disconnect.mutate()}>
            {t("googleDisconnect")}
          </button>
        </div>
      ) : status.data.configured ? (
        <a href="/api/google/start">{t("googleConnect")}</a>
      ) : (
        <p>{t("googleNotConfigured")}</p>
      )}
    </section>
  );
}

function googleTemplate(event: CalEvent): string {
  const text = encodeURIComponent(event.title);
  if (event.all_day) {
    const start = event.civil_date.replaceAll("-", "");
    const next = addDays(event.civil_date, 1).replaceAll("-", "");
    return `https://calendar.google.com/calendar/render?action=TEMPLATE&text=${text}&dates=${start}/${next}`;
  }
  const start = toGoogleUtc(event.starts_at);
  const end = toGoogleUtc(event.ends_at ?? addHours(event.starts_at, 1));
  return `https://calendar.google.com/calendar/render?action=TEMPLATE&text=${text}&dates=${start}/${end}`;
}

function toGoogleUtc(iso: string): string {
  return new Date(iso).toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
}

function addHours(iso: string, hours: number): string {
  return new Date(new Date(iso).getTime() + hours * 60 * 60 * 1000).toISOString();
}

function toJerusalemIso(date: string, time: string): string {
  const [year, month, day] = date.split("-").map(Number);
  const [hour, minute] = time.split(":").map(Number);
  const guess = new Date(Date.UTC(year, month - 1, day, hour, minute));
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "Asia/Jerusalem",
    hourCycle: "h23",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).formatToParts(guess);
  const read = (type: string) => Number(parts.find((part) => part.type === type)?.value);
  const asUtc = Date.UTC(read("year"), read("month") - 1, read("day"), read("hour"), read("minute"));
  const delta = asUtc - guess.getTime();
  return new Date(guess.getTime() - delta).toISOString();
}
