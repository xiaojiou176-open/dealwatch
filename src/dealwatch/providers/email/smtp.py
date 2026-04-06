from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import uuid4

from dealwatch.infra.config import Settings
from dealwatch.infra.mailer import EmailNotifier
from dealwatch.providers.email.base import EmailDispatchPayload, EmailDispatchResult


@dataclass(slots=True)
class SmtpFallbackEmailProvider:
    settings: Settings

    async def send(self, payload: EmailDispatchPayload) -> EmailDispatchResult:
        notifier = EmailNotifier(self.settings)
        sent = await asyncio.to_thread(
            notifier.send_custom_report,
            payload.html_body,
            payload.subject,
            payload.metadata.get("subject_date", "n/a"),
        )
        if not sent:
            raise RuntimeError("smtp_dispatch_failed")
        return EmailDispatchResult(
            provider="smtp",
            status="sent",
            message_id=f"smtp-{uuid4()}",
            payload={"recipient": payload.recipient, "template_key": payload.template_key},
        )
