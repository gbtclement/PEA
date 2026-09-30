import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from typing import Protocol

from app.core.config import Settings


class Mailer(Protocol):
    def send(self, *, to: str, subject: str, html: str, text: str, headers: dict[str, str]) -> None: ...


class SmtpMailer:
    def __init__(self, host: str, port: int, user: str, password: str, tls: str, sender: str) -> None:
        self.host, self.port, self.user, self.password, self.tls, self.sender = host, port, user, password, tls, sender

    def send(self, *, to: str, subject: str, html: str, text: str, headers: dict[str, str]) -> None:
        message = EmailMessage()
        message["From"] = self.sender
        message["To"] = to
        message["Subject"] = subject
        message["Date"] = formatdate(localtime=True)
        message["Message-ID"] = make_msgid(domain=self.sender.rsplit("@", 1)[-1].rstrip(">"))
        for name, value in headers.items():
            message[name] = value
        message.set_content(text)
        message.add_alternative(html, subtype="html")
        smtp_class = smtplib.SMTP_SSL if self.tls == "ssl" else smtplib.SMTP
        with smtp_class(self.host, self.port, timeout=20) as smtp:
            if self.tls == "starttls":
                smtp.starttls(context=ssl.create_default_context())
            if self.user:
                smtp.login(self.user, self.password)
            smtp.send_message(message)


def mailer_from_settings(settings: Settings) -> Mailer | None:
    if not settings.smtp_host:
        return None
    return SmtpMailer(settings.smtp_host, settings.smtp_port, settings.smtp_user, settings.smtp_password,
                      settings.smtp_tls, settings.mail_from)
