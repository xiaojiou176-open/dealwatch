from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from dealwatch.stores import STORE_REGISTRY
@dataclass(slots=True)
class ResolvedTarget:
    submitted_url: str
    normalized_url: str
    product_url: str
    store_key: str
    supported: bool
    error_code: str | None = None


def normalize_url(raw_url: str) -> str:
    parsed = urlsplit(raw_url.strip())
    return urlunsplit(
        (
            parsed.scheme or "https",
            parsed.netloc.lower(),
            parsed.path.rstrip("/") or "/",
            "",
            "",
        )
    )


def resolve_store_for_url(raw_url: str) -> ResolvedTarget:
    submitted = raw_url.strip()
    normalized = normalize_url(submitted)
    parsed = urlsplit(normalized)
    host = parsed.netloc

    for store_key, adapter_cls in STORE_REGISTRY.items():
        store_host = urlsplit(adapter_cls.base_url).netloc.lower().strip()
        if host != store_host:
            continue
        product_url = adapter_cls.normalize_product_url(normalized)
        if product_url is None:
            return ResolvedTarget(
                submitted_url=submitted,
                normalized_url=normalized,
                product_url=normalized,
                store_key=store_key,
                supported=False,
                error_code="unsupported_store_path",
            )

        return ResolvedTarget(
            submitted_url=submitted,
            normalized_url=product_url,
            product_url=product_url,
            store_key=store_key,
            supported=True,
        )

    return ResolvedTarget(
        submitted_url=submitted,
        normalized_url=normalized,
        product_url=normalized,
        store_key="unsupported",
        supported=False,
        error_code="unsupported_store_host",
    )
