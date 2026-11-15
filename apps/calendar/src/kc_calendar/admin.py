"""Set the parent password hash from PARENT_PASSWORD.

This does not create an account. If no parent exists yet, start the service once
so bootstrap can create it. Changing PARENT_PASSWORD and running this command
replaces the stored hash. The plaintext password stays in the secret store.
"""

import asyncio

from sqlalchemy import select

from kc_calendar.db.models import ParentAccount
from kc_calendar.db.session import make_engine, make_session_factory
from kc_calendar.security import hash_password
from kc_calendar.settings import Settings


async def _run() -> None:
    settings = Settings()  # type: ignore[call-arg]
    engine = make_engine(settings)
    factory = make_session_factory(engine)
    async with factory() as session:
        account = await session.scalar(select(ParentAccount).limit(1))
        if account is None:
            raise SystemExit("no parent account; start calendar once to bootstrap")
        account.password_hash = hash_password(settings.parent_password)
        await session.commit()
    await engine.dispose()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
