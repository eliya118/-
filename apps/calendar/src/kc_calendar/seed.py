"""Idempotent parent bootstrap. Startup does this too; `make seed` calls it again."""

import asyncio

from kc_calendar.bootstrap import bootstrap
from kc_calendar.db.session import make_engine, make_session_factory
from kc_calendar.settings import Settings


async def _run() -> None:
    settings = Settings()  # type: ignore[call-arg]
    engine = make_engine(settings)
    try:
        await bootstrap(make_session_factory(engine), settings)
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
