.PHONY: up test lint seed

up:
	docker compose up --build

test:
	docker compose --profile test run --rm --build calendar-test
	docker compose --profile test run --rm --build intake-test
	docker compose --profile test run --rm --build ideas-test
	docker compose --profile test run --rm --build notifier-test
	docker compose --profile test run --rm --build web-test

lint:
	docker compose --profile test run --rm --build calendar-test ruff check apps libs
	docker compose --profile test run --rm --build calendar-test pyright
	docker compose --profile test run --rm --build web-test pnpm typecheck
	docker compose --profile test run --rm --build web-test pnpm lint

seed:
	docker compose run --rm calendar python -m kc_calendar.seed
