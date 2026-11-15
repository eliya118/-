# Implementation steps

This is the build log for the kids calendar. Each section says why the step exists, which files it adds, and what “done” means, then what actually landed and how it was checked.

The Python package inside `apps/calendar` is named `kc_calendar`, not `calendar`. The standard-library module `calendar` is what `hdate` imports (`isleap`, `timegm`). A package of the same name cannot sit on `sys.path`. The service, image, and Compose name stay `calendar`.

## 1. Containers, Compose, and health checks

The app is five processes plus Postgres, Redis, and Mailpit. This step exists so `docker compose up` is the path every later step boots, and so each process can tell Compose when it is up.

Folders and files:

- `compose.yml`, `Makefile`, `.env.example`, `.dockerignore`
- `apps/web`, `apps/calendar`, `apps/intake`, `apps/ideas`, `apps/notifier` — one Dockerfile each
- `deploy/postgres/init.sh` — three databases and three roles
- `.github/workflows/ci.yml` — test and lint inside the images
- A `/health` and `/ready` route on each Python service

Done means: `make up` builds the five images and starts Postgres, Redis, and Mailpit; each app answers `/health`; calendar, ideas, and notifier report `/ready` only when their database (and Redis, where they use it) answers.

What landed: Compose builds five non-root images from pinned bases (Python 3.13.18, Node 22.22.0, nginx-unprivileged 1.29.3, Postgres 17.7, Redis 7.4.7, Mailpit v1.27.1), each with a digest. Postgres init creates `calendar_app`, `ideas_app`, and `notifier_app` and revokes public connect. Web listens on 8080 and is published on 5173. Its health check uses `curl` because that nginx image does not have `wget`.

Checked: `docker compose up --build -d` came up with all eight services healthy. `GET /health` on calendar returned ok. Web returned 200 on `/`.

## 2. Calendar, Hebrew dates, and the week grid

Parents need a week they can read: civil dates, Hebrew dates, Shabbat, and Israel holidays, plus a way to add a child and an event by hand.

Folders and files:

- `libs/hebrewcal` — `hdate` wrapper, Israel schedule, `diaspora=False`
- `libs/contracts` — event and draft models
- `apps/calendar` — schema, Alembic, seeded parent, session cookie, children, events, week route
- `apps/web` — Hebrew-default RTL shell and a Sunday-first week grid

Done means: a seeded parent can sign in, save a child, create an event, and see that week with a Hebrew date beside each civil date. Shavuot is one day. A Friday that is not a festival eve shows candle-lighting.

What landed: Tables for family, parent, session, child, event, event child, outbox, and idempotency. Startup seeds one parent from `PARENT_EMAIL` / `PARENT_PASSWORD` when none exists (`parent@example.com` / `local-parent-password` in Compose). The cookie is `kc_session`, HttpOnly, SameSite=Lax. The week route rejects a date that is not a Sunday. The grid renders the server’s day list in order and does not invent Hebrew strings.

Checked: `pytest` inside the calendar image, 15 passed, including the Sunday rule, DST offsets, longest-name tokenization, `remind_at`, and age bands. Hebrew examples in `libs/hebrewcal/tests/test_hebrew.py` passed in that same run (Shavuot 5785 is 2025-06-02 only; `after_chag` inside that day is 2025-06-03; Rosh Hashanah is two days; 16 Nisan is chol hamoed). Against the running stack, `GET /api/weeks/2025-06-01` returned Erev Shavuot, Shavuot, Shabbat on 2025-06-07, candle-lighting on the Friday, and havdalah after Shabbat. In the browser at `http://127.0.0.1:5173` the week of 15 Nov 2026 showed כסלו תשפ״ז, Saturday marked שבת with havdalah, and Friday candle-lighting.

## 3. Intake and the fake language model

A parent should be able to type one Hebrew or English sentence. The date math stays in Python. Tests must pass with no API key.

Folders and files:

- `libs/llm` — `LanguageModel`, fake adapter, OpenAI adapter
- `apps/intake` — phrase table, resolver, `POST /internal/parse`

Done means: a few fixed phrases plus the date resolver produce a draft, and an empty OpenAI key does not pretend to parse.

What landed: Compose defaults `LLM_PROVIDER=fake`. The fake adapter handles tomorrow / מחר, Sunday / יום ראשון, Shabbat / שבת, erev Shabbat / ערב שבת, erev chag / ערב חג, and after the holiday / אחרי החג, with a clock time or “all day”. Missing time, missing child, or an unknown name comes back as a clarification. `LLM_PROVIDER=openai` with an empty key raises and the calendar preview returns 503; the manual form still works. Calendar replaces child names with `child_N` before the call and does not send the names.

Checked: intake image tests, 4 passed (Hebrew and English phrases, fixture override, openai-without-a-key). Through the web proxy: “dentist tomorrow at 16:00 for Noa” and “רופא מחר בשעה 16:00 לנועה” both returned a ready draft for 16 Nov 2026 16:00. Confirming them showed both events on the week. In the browser, “park tomorrow at 10:00 for Noa” previewed and then appeared on 16 Nov at 10:00.

## 4. Outbox, notifier, and Mailpit

A reminder must be sent once. A newer edit must cancel the older one. Local mail goes to Mailpit, not the public internet.

Folders and files:

- `apps/calendar` outbox row and relay (`stream:calendar.events`)
- `apps/notifier` — consumer, reminder state machine, SMTP channel
- Mailpit in Compose on 8025 / 1025

Done means: creating an event writes an outbox row in the same transaction, the notifier turns it into one reminder, and a due reminder shows up in Mailpit. Sending the same reminder again does not send a second mail.

What landed: The relay XADDs then sets `published_at`. The notifier uses consumer group `notifier`, claims idle messages after 60 seconds, and also polls due rows every 5 seconds. Both paths call the same send function; the status change from `scheduled` to `sending` is the lock. The reminder key is `event_id:generation:channel`. The reminder table has two columns the plan’s sketch did not list, `starts_at` and `locale`, so the email can show the local time and follow the event language without calling calendar back.

Checked: notifier image tests, 4 passed (a second send of the same generation is a no-op, a newer generation cancels the older row, a null `remind_at` schedules nothing, a failed send retries). Live: an event with `remind_offset_minutes` 0 and a start about 40 seconds ahead produced one Mailpit message, subject “Reminder: mail check”, to `parent@example.com`.

## 5. Ideas

After a child has a birth year and month, the parent should see a few activity ideas and breakfast/dinner ideas. No API key means the seed catalog.

Folders and files:

- `apps/ideas` — seed catalog, cache table, `GET /internal/activities` and `/internal/meals`
- `apps/web` ideas page

Done means: a request with an age band returns seed items, and the page shows them. Ideas never receives a child id or a name.

Checked: ideas image test, 1 passed (catalog picks the band, then falls back). Live `GET /api/ideas/activities` for Noa (band 6–8) returned Hebrew seed items, `source: seed`, `degraded: false`. Breakfast did the same. The ideas page in the browser showed activity, breakfast, and dinner cards.

## 6. OpenAI and Resend, selected only by environment

The vendor adapters exist so a deployed environment can turn them on without a code change. Local Compose does not call them.

Folders and files:

- `libs/llm/src/llm/openai.py`
- `apps/notifier/src/notifier/channels/email.py` (`ResendEmailChannel` when `EMAIL_MODE=resend`)
- `.env.example` — `LLM_MODEL`, `LLM_API_KEY`, `RESEND_API_KEY`, `EMAIL_MODE`

Done means: the model id is read from `LLM_MODEL` and is not hard-coded in the adapter, and Mailpit remains the local channel.

What landed: that split is in place. It was not called against OpenAI or Resend. See the leftover list.

Checked: the intake test that sets `LLM_PROVIDER=openai` and an empty key fails closed. `EMAIL_MODE` defaults to `mailpit` in Compose, which is the path that delivered the Mailpit message above.

## 7. Render blueprint

The blueprint is the later deploy shape. It is not how you run the app today.

Folders and files:

- `deploy/render.yaml` — Frankfurt, Docker runtime, web public, the other four services private, Key Value, Postgres 17

Done means: the file describes the five services, Redis, and Postgres. Applying it and checking the managed Redis command is still a manual step.

What landed: the blueprint is committed. `CALENDAR_UPSTREAM` is set there, but `apps/web/nginx.conf` still proxies to `http://calendar:8000`. That is correct for Compose. On Render it only works if the private service is reachable as `calendar`.

## Leftovers

- Playwright smoke (log in, open the week, see a Hebrew date) is not in CI. The same path was checked by hand in a browser against this Compose stack.
- No automated test that talks to Postgres for the week query or the outbox transaction. Those rules are covered by unit tests plus the live stack.
- No committed OpenAPI diff.
- Managed Redis command check, one real Resend email, and one live Hebrew preview through OpenAI were not run.
- `nginx.conf` does not read `CALENDAR_UPSTREAM`.
