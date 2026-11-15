"""Give service modules the environment they expect if a test imports them."""

import os

os.environ.setdefault("CALENDAR_DATABASE_URL", "postgresql+asyncpg://calendar_app:calendar@localhost:5432/calendar")
os.environ.setdefault("IDEAS_DATABASE_URL", "postgresql+asyncpg://ideas_app:ideas@localhost:5432/ideas")
os.environ.setdefault("NOTIFIER_DATABASE_URL", "postgresql+asyncpg://notifier_app:notifier@localhost:5432/notifier")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("INTERNAL_API_TOKEN", "test-internal-token")
os.environ.setdefault("PARENT_EMAIL", "parent@example.com")
os.environ.setdefault("PARENT_PASSWORD", "local-parent-password")
os.environ.setdefault("WEB_ORIGIN", "http://localhost:5173")
os.environ.setdefault("LLM_PROVIDER", "fake")
os.environ.setdefault("LLM_API_KEY", "")
os.environ.setdefault("LLM_MODEL", "gpt-4.1-mini")
os.environ.setdefault("EMAIL_MODE", "mailpit")
os.environ.setdefault("SMTP_URL", "smtp://localhost:1025")
os.environ.setdefault("EMAIL_FROM", "calendar@localhost")
os.environ.setdefault("NOTIFIER_CHANNELS", "email")
os.environ.setdefault("APP_TIMEZONE", "Asia/Jerusalem")
