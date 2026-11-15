from dataclasses import dataclass


class TransientError(Exception):
    """Retry. The vendor did not accept the message."""


class PermanentError(Exception):
    """Stop. The address was rejected or the configuration is wrong."""


@dataclass(frozen=True)
class Delivery:
    idempotency_key: str
    locale: str
    title: str
    local_start: str
    destination: str


class Channel:
    name: str

    def send(self, delivery: Delivery) -> None:
        raise NotImplementedError
