import uuid


def new_id() -> uuid.UUID:
    factory = getattr(uuid, "uuid7", None)
    if factory is not None:
        return factory()
    return uuid.uuid4()
