import asyncio
import smtplib
from email.message import EmailMessage

from app.core.config import MailSettings, cfg


class MailError(RuntimeError):
    """Raised when SMTP delivery fails or is not configured."""


class MailClient:
    """SMTP sender driven by the `MAIL__*` settings; disabled until configured."""

    def __init__(self, settings: MailSettings | None = None) -> None:
        self._settings = settings if settings is not None else cfg.mail

    @property
    def ready(self) -> bool:
        return self._settings.ready

    async def send(self, *, to: str, subject: str, body: str) -> None:
        if not self.ready:
            raise MailError("SMTP is not configured (set MAIL__HOST and MAIL__FROM_ADDRESS)")
        if not to.strip():
            raise MailError("Recipient address is not set — open «Интеграции» and save one")

        message = EmailMessage()
        message["From"] = self._settings.from_address
        message["To"] = to.strip()
        message["Subject"] = subject
        message.set_content(body)

        await asyncio.to_thread(self._send_sync, message)

    def _send_sync(self, message: EmailMessage) -> None:
        with smtplib.SMTP(
            self._settings.host, self._settings.port, timeout=self._settings.timeout
        ) as client:
            if self._settings.use_tls:
                client.starttls()
            if self._settings.username and self._settings.password is not None:
                client.login(self._settings.username, self._settings.password.get_secret_value())
            client.send_message(message)
