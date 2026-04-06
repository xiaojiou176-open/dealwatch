from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(slots=True)
class EmailDispatchPayload:
    recipient: str
    subject: str
    html_body: str
    template_key: str
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class EmailDispatchResult:
    provider: str
    status: str
    message_id: str | None = None
    payload: dict | None = None


class EmailProvider(Protocol):
    async def send(self, payload: EmailDispatchPayload) -> EmailDispatchResult:
        raise NotImplementedError
