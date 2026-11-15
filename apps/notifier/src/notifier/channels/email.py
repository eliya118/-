"""Plain-text email. Mailpit locally, Resend when EMAIL_MODE=resend."""

import smtplib
from email.message import EmailMessage
from urllib.parse import urlparse

import httpx

from notifier.channels.protocol import Channel, Delivery, PermanentError, TransientError


def render(delivery: Delivery) -> tuple[str, str]:
    if delivery.locale == "he":
        subject = f"תזכורת: {delivery.title}"
        body = f"תזכורת: {delivery.title}\nמתי: {delivery.local_start}\n"
    else:
        subject = f"Reminder: {delivery.title}"
        body = f"Reminder: {delivery.title}\nWhen: {delivery.local_start}\n"
    return subject, body


class SmtpEmailChannel(Channel):
    name = "email"

    def __init__(self, smtp_url: str, sender: str) -> None:
        parsed = urlparse(smtp_url)
        if parsed.scheme not in {"smtp", "smtps"}:
            raise PermanentError("SMTP_URL must start with smtp://")
        self._host = parsed.hostname or "localhost"
        self._port = parsed.port or 1025
        self._sender = sender

    def send(self, delivery: Delivery) -> None:
        subject, body = render(delivery)
        message = EmailMessage()
        message["From"] = self._sender
        message["To"] = delivery.destination
        message["Subject"] = subject
        message.set_content(body)
        try:
            with smtplib.SMTP(self._host, self._port, timeout=10) as client:
                client.send_message(message)
        except (TimeoutError, OSError, smtplib.SMTPException) as exc:
            raise TransientError("smtp failed") from exc


class ResendEmailChannel(Channel):
    name = "email"

    def __init__(self, api_key: str, sender: str) -> None:
        self._api_key = api_key
        self._sender = sender

    def send(self, delivery: Delivery) -> None:
        if not self._api_key:
            raise PermanentError("RESEND_API_KEY is empty")
        subject, body = render(delivery)
        try:
            response = httpx.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "from": self._sender,
                    "to": [delivery.destination],
                    "subject": subject,
                    "text": body,
                },
                timeout=10.0,
            )
        except httpx.HTTPError as exc:
            raise TransientError("resend transport failed") from exc
        if response.status_code in {429, 500, 502, 503, 504}:
            raise TransientError(f"resend status {response.status_code}")
        if response.status_code >= 400:
            raise PermanentError(f"resend status {response.status_code}")


class RecordingChannel(Channel):
    """Test double. Records deliveries and does not touch the network."""

    name = "email"

    def __init__(self) -> None:
        self.sent: list[Delivery] = []

    def send(self, delivery: Delivery) -> None:
        self.sent.append(delivery)


def build_email_channel(mode: str, smtp_url: str, resend_api_key: str, sender: str) -> Channel:
    if mode == "resend":
        return ResendEmailChannel(resend_api_key, sender)
    return SmtpEmailChannel(smtp_url, sender)
