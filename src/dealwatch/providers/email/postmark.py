from __future__ import annotations

from dataclasses import dataclass

import httpx

from dealwatch.infra.config import Settings
from dealwatch.providers.email.base import EmailDispatchPayload, EmailDispatchResult


@dataclass(slots=True)
class PostmarkEmailProvider:
    settings: Settings
    endpoint: str = "https://api.postmarkapp.com/email"

    async def send(self, payload: EmailDispatchPayload) -> EmailDispatchResult:
        token = self.settings.POSTMARK_SERVER_TOKEN.get_secret_value().strip()
        if not token:
            raise RuntimeError("POSTMARK_SERVER_TOKEN is not configured")

        body = {
            "From": self.settings.POSTMARK_FROM_EMAIL,
            "To": payload.recipient,
            "Subject": payload.subject,
            "HtmlBody": payload.html_body,
            "MessageStream": self.settings.POSTMARK_MESSAGE_STREAM,
            "Metadata": payload.metadata,
        }
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Postmark-Server-Token": token,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(self.endpoint, headers=headers, json=body)
            response.raise_for_status()
            data = response.json()
        return EmailDispatchResult(
            provider="postmark",
            status="sent",
            message_id=str(data.get("MessageID", "")) or None,
            payload=data,
        )
