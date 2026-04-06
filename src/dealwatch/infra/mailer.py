from __future__ import annotations

import logging
import os
import smtplib
import ssl
import time
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import Final, Iterable

from dealwatch.infra.config import Settings


#########################################################
# Constants
#########################################################
_DEFAULT_PORT: Final[int] = 587
_SMTP_TIMEOUT: Final[int] = 30
_RETRY_ATTEMPTS: Final[int] = 3
_RETRY_BASE_DELAY: Final[float] = 0.8


#########################################################
# Mailer
#########################################################
@dataclass(slots=True)
class EmailNotifier:
    settings: Settings
    logger: logging.Logger = field(init=False, repr=False)

    HTML_TEMPLATE: Final[str] = (
        "<div style=\"font-family: Arial, Helvetica, sans-serif;"
        "background:#f7f9f7;padding:16px;\">"
        "<div style=\"max-width:760px;margin:0 auto;background:#ffffff;"
        "border:1px solid #e6e6e6;padding:16px;\">"
        "<div style=\"font-size:22px;font-weight:700;color:#0b5d1e;"
        "margin-bottom:4px;\">DealWatch Daily Report</div>"
        "<div style=\"font-size:12px;color:#666;margin-bottom:16px;\">"
        "{{subject_date}}</div>"
        "<div>{{content}}</div>"
        "<div style=\"margin-top:16px;font-size:12px;color:#777;\">"
        "Price style: "
        "<span style=\"color:#c0392b;font-weight:700;font-size:16px;\">"
        "$1.99</span>"
        "<span style=\"color:#999;text-decoration:line-through;"
        "margin-left:8px;\">$2.99</span>"
        "</div>"
        "</div>"
        "</div>"
    )

    def __post_init__(self) -> None:
        self.logger = logging.getLogger(__name__)

    def send_daily_report(self, html_content: str, subject_date: str) -> bool:
        subject = f"DealWatch Daily Report - {subject_date}"
        return self.send_custom_report(
            html_content=html_content,
            subject=subject,
            subject_date=subject_date,
        )

    def send_custom_report(
        self,
        html_content: str,
        subject: str,
        subject_date: str,
    ) -> bool:
        host, port = self._parse_smtp_host(self.settings.SMTP_HOST)
        sender = self.settings.SMTP_USER.strip()
        recipients = self._resolve_recipients(sender)

        if not host:
            self.logger.error("SMTP_HOST is empty, cannot send email.")
            return False

        if not recipients:
            self.logger.error("No recipients configured, cannot send email.")
            return False

        html_body = (
            self.HTML_TEMPLATE
            .replace("{{content}}", html_content)
            .replace("{{subject_date}}", subject_date)
        )

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = sender or "dealwatch@localhost"
        message["To"] = ", ".join(recipients)
        message.set_content("This email requires an HTML-capable client.")
        message.add_alternative(html_body, subtype="html", charset="utf-8")

        password = os.getenv("SMTP_PASSWORD", "")
        if not password:
            password = os.getenv("SMTP_PASS", "")

        for attempt in range(1, _RETRY_ATTEMPTS + 1):
            try:
                self._send_smtp(
                    host=host,
                    port=port,
                    sender=message["From"],
                    recipients=recipients,
                    message=message,
                    username=sender,
                    password=password,
                )
                return True
            except Exception as exc:
                self.logger.exception("Email send failed (attempt %s): %s", attempt, exc)
                if attempt >= _RETRY_ATTEMPTS:
                    self.logger.error("Email send failed after retries, giving up.")
                    return False
                time.sleep(_RETRY_BASE_DELAY * attempt)
        return False

    #########################################################
    # Internal
    #########################################################
    @staticmethod
    def _parse_smtp_host(host: str) -> tuple[str, int]:
        host = (host or "").strip()
        if not host:
            return "", _DEFAULT_PORT

        if ":" in host:
            maybe_host, maybe_port = host.rsplit(":", 1)
            if maybe_port.isdigit():
                return maybe_host, int(maybe_port)

        return host, _DEFAULT_PORT

    @staticmethod
    def _resolve_recipients(sender: str) -> list[str]:
        raw = os.getenv("SMTP_TO", "").strip()
        if raw:
            return [item.strip() for item in raw.split(",") if item.strip()]

        if sender:
            return [sender]

        return []

    def _send_smtp(
        self,
        host: str,
        port: int,
        sender: str,
        recipients: Iterable[str],
        message: EmailMessage,
        username: str,
        password: str,
    ) -> None:
        context = ssl.create_default_context()

        try:
            with smtplib.SMTP(host, port, timeout=_SMTP_TIMEOUT) as smtp:
                smtp.ehlo()
                if smtp.has_extn("starttls"):
                    smtp.starttls(context=context)
                    smtp.ehlo()
                if username and password:
                    smtp.login(username, password)
                smtp.send_message(message, from_addr=sender, to_addrs=list(recipients))
        except smtplib.SMTPException as exc:
            self.logger.exception("SMTP error: %s", exc)
            raise
