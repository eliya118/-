# Kids calendar

One family. Parents sign in, add children, and turn a Hebrew or English sentence into an event. The week shows the civil date beside the Hebrew date, with Shabbat and Israel holidays. Reminders go to Mailpit locally. Activity and meal ideas come from a seed catalog when no model key is set.

Docker is the only way to run it. Copy `.env.example` to `.env` if you want to change the defaults, then:

```sh
make up
```

Open http://localhost:5173. Mailpit is at http://localhost:8025. The seeded parent is `parent@example.com` / `local-parent-password`.

`make test` and `make lint` run inside the images. `make seed` sets the parent again if the account is missing.

To change the password after the account exists:

```sh
docker compose run --rm calendar python -m kc_calendar.admin
```

That writes a new hash from `PARENT_PASSWORD`. It does not create the account.

With `LLM_PROVIDER=fake` (the local default) intake understands a few fixed phrases, including “tomorrow”, “שבת”, “ערב חג”, and “אחרי החג”, plus a clock time and a `child_N` token. The calendar replaces a child’s name with that token before the call. `LLM_PROVIDER=openai` with an empty key makes preview return 503; the manual form still saves an event. `EMAIL_MODE=resend` sends through Resend; `mailpit` uses the local SMTP server.

The architecture notes live with the project. `docs/implementation-steps.md` is the build log.
