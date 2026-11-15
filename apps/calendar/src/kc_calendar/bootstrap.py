import logging

from contracts.events import ContactUpdated
from sqlalchemy import select

from kc_calendar.db.models import Family, Outbox, ParentAccount
from kc_calendar.domain.timeutil import now_jerusalem
from kc_calendar.ids import new_id
from kc_calendar.security import hash_password
from kc_calendar.settings import Settings

log = logging.getLogger("calendar.bootstrap")


async def bootstrap(session_factory, settings: Settings) -> None:  # type: ignore[no-untyped-def]
    async with session_factory() as session:
        existing = await session.scalar(select(ParentAccount).limit(1))
        if existing is not None:
            return
        family = Family(id=new_id(), timezone=settings.app_timezone, locale="he")
        session.add(family)
        await session.flush()
        email = settings.parent_email.strip().lower()
        session.add(
            ParentAccount(
                id=new_id(),
                family_id=family.id,
                email=email,
                password_hash=hash_password(settings.parent_password),
            )
        )
        payload = ContactUpdated(family_id=family.id, email=email, locale="he").model_dump(mode="json")
        session.add(
            Outbox(id=new_id(), type="family.contact_updated", payload=payload, created_at=now_jerusalem(), attempts=0)
        )
        await session.commit()
        log.info("seeded parent", extra={"family_id": str(family.id)})
