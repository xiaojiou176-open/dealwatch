from dealwatch.providers.email.base import EmailDispatchPayload, EmailDispatchResult, EmailProvider
from dealwatch.providers.email.postmark import PostmarkEmailProvider
from dealwatch.providers.email.smtp import SmtpFallbackEmailProvider

__all__ = [
    "EmailDispatchPayload",
    "EmailDispatchResult",
    "EmailProvider",
    "PostmarkEmailProvider",
    "SmtpFallbackEmailProvider",
]
