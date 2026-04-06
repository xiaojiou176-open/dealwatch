from __future__ import annotations

import asyncio
import logging
import math
from datetime import datetime, timezone
from typing import Final, List

from dealwatch.core.models import DealEvent, Offer, RunStats
from dealwatch.core.rules import RulesEngine
from dealwatch.core.validator import DataValidator
from dealwatch.infra.config import Settings
from dealwatch.infra.playwright_client import PlaywrightClient
from dealwatch.legacy.db_repo import DatabaseRepository
from dealwatch.stores.base_adapter import BaseStoreAdapter, SkipParse


#########################################################
# Constants
#########################################################
_MAX_CONCURRENCY: Final[int] = 4
_PROGRESS_STEPS: Final[int] = 5
_BLOCKED_SIGNAL: Final[str] = "IP_RESTRICTED"


#########################################################
# Pipeline
#########################################################
class MonitoringPipeline:
    def __init__(
        self,
        repo: DatabaseRepository,
        client: PlaywrightClient,
        settings: Settings,
    ) -> None:
        self.repo = repo
        self.client = client
        self.settings = settings
        self.rules = RulesEngine(
            min_drop_amount=settings.RULE_MIN_DROP_AMOUNT,
            min_drop_pct=settings.RULE_MIN_DROP_PCT,
            anomaly_min_samples=settings.ANOMALY_MIN_SAMPLES,
            anomaly_iqr_multiplier=settings.ANOMALY_IQR_MULTIPLIER,
            anomaly_zscore_threshold=settings.ANOMALY_ZSCORE_THRESHOLD,
            anomaly_zero_var_pct=settings.ANOMALY_ZERO_VAR_PCT,
            anomaly_zero_var_abs=settings.ANOMALY_ZERO_VAR_ABS,
        )
        self.validator = DataValidator(
            min_price=settings.VALIDATOR_MIN_PRICE,
            max_price=settings.VALIDATOR_MAX_PRICE,
            min_title_length=settings.VALIDATOR_MIN_TITLE_LENGTH,
        )
        self.logger = logging.getLogger(__name__)
        self.last_stats: RunStats | None = None
        self.last_failed_urls: list[str] = []
        self.last_error_snippet: str = ""

    async def run_store(self, adapter: BaseStoreAdapter) -> List[DealEvent]:
        start_time = datetime.now(timezone.utc)
        try:
            urls = await adapter.discover_deals()
        except Exception as exc:
            adapter.logger.exception("discover_deals failed: %s", exc)
            self._set_run_stats(
                store_id=adapter.store_id,
                start_time=start_time,
                discovered_count=0,
                parsed_count=0,
                error_count=1,
                confirmed_deals_count=0,
                skipped_count=0,
                failed_urls=[],
                error_snippet=str(exc),
            )
            return []

        total = len(urls)
        if total == 0:
            adapter.logger.info("[%s] No deals discovered.", adapter.store_id)
            self._set_run_stats(
                store_id=adapter.store_id,
                start_time=start_time,
                discovered_count=0,
                parsed_count=0,
                error_count=0,
                confirmed_deals_count=0,
                skipped_count=0,
                failed_urls=[],
                error_snippet="",
            )
            return []

        semaphore = asyncio.Semaphore(_MAX_CONCURRENCY)
        progress_marks = self._build_progress_marks(total)
        failed_urls: list[str] = []
        error_snippets: list[str] = []
        error_lock = asyncio.Lock()
        skipped_items: list[tuple[str, str]] = []
        skip_lock = asyncio.Lock()

        async def _parse_url(url: str) -> Offer | None:
            async with semaphore:
                try:
                    return await adapter.parse_product(url)
                except SkipParse as exc:
                    async with skip_lock:
                        skipped_items.append((url, exc.reason.value))
                    return None
                except (StopIteration, StopAsyncIteration):
                    raise
                except Exception as exc:
                    adapter.logger.exception("parse_product failed for %s: %s", url, exc)
                    async with error_lock:
                        failed_urls.append(url)
                        error_snippets.append(str(exc))
                    return None

        tasks = [asyncio.create_task(_parse_url(url)) for url in urls]
        try:
            offers = await asyncio.gather(*tasks)
        except (StopIteration, StopAsyncIteration) as exc:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

            blocked_url = self._extract_blocked_url(str(exc))
            if blocked_url:
                failed_urls.append(blocked_url)
            error_snippets.append(str(exc))

            self._set_run_stats(
                store_id=adapter.store_id,
                start_time=start_time,
                discovered_count=total,
                parsed_count=0,
                error_count=len(failed_urls) + 1,
                confirmed_deals_count=0,
                skipped_count=len(skipped_items),
                failed_urls=failed_urls,
                error_snippet=str(exc),
            )
            adapter.logger.error(
                "[%s] Stop signal triggered: %s",
                adapter.store_id,
                exc,
            )
            return []

        parsed_count = 0
        deal_count = 0
        processed = 0
        error_count = 0
        results: list[DealEvent] = []

        for offer in offers:
            processed += 1

            if offer is None:
                self._log_progress(adapter, processed, total, progress_marks)
                continue

            parsed_count += 1

            try:
                if not self.validator.validate_offer(offer):
                    error_count += 1
                    error_snippets.append("validation_failed")
                    self._log_progress(adapter, processed, total, progress_marks)
                    continue

                context_hash = offer.context.get_hash()
                history = await self.repo.get_price_series(
                    offer.store_id,
                    offer.product_key,
                    context_hash,
                    lookback_days=self.settings.ANOMALY_LOOKBACK_DAYS,
                    limit=self.settings.ANOMALY_MAX_SAMPLES,
                )
                anomaly_reason = None
                if self.settings.ANOMALY_ENABLED:
                    is_anomaly, reason = self.rules.is_anomalous_price(
                        offer.price,
                        history,
                    )
                    if is_anomaly:
                        anomaly_reason = reason
                        if not self.settings.ANOMALY_MARK_ONLY:
                            error_count += 1
                            error_snippets.append(f"anomaly:{reason.value if reason else 'unknown'}")
                            self._log_progress(adapter, processed, total, progress_marks)
                            continue

                last_price = await self.repo.get_last_price(
                    offer.store_id,
                    offer.product_key,
                    context_hash,
                    max_age_days=self.settings.PRICE_HISTORY_KEEP_DAYS,
                )
                historical_low = None
                if last_price is not None:
                    historical_low = await self.repo.get_historical_low(
                        offer.store_id,
                        offer.product_key,
                        context_hash,
                    )
                deal = self.rules.analyze_drop(
                    offer,
                    last_price,
                    historical_low=historical_low,
                    anomaly_reason=anomaly_reason,
                )

                await self.repo.upsert_product(offer)
                await self.repo.insert_price_point(offer)

                if deal is not None:
                    results.append(deal)
                    deal_count += 1
            except Exception as exc:
                error_count += 1
                error_snippets.append(str(exc))
                adapter.logger.exception(
                    "audit/persist failed for %s: %s",
                    offer.product_key,
                    exc,
                )

            self._log_progress(adapter, processed, total, progress_marks)

        adapter.logger.info(
            "[%s] Run complete. total=%s, parsed=%s, deals=%s",
            adapter.store_id,
            total,
            parsed_count,
            deal_count,
        )

        error_count += len(failed_urls)
        skipped_count = len(skipped_items)
        self._set_run_stats(
            store_id=adapter.store_id,
            start_time=start_time,
            discovered_count=total,
            parsed_count=parsed_count,
            error_count=error_count,
            confirmed_deals_count=deal_count,
            skipped_count=skipped_count,
            failed_urls=failed_urls,
            error_snippet=error_snippets[-1] if error_snippets else "",
        )

        return results

    #########################################################
    # Internal
    #########################################################
    @staticmethod
    def _build_progress_marks(total: int) -> set[int]:
        if total <= 0:
            return set()

        marks = {
            max(1, math.ceil(total * step / _PROGRESS_STEPS))
            for step in range(1, _PROGRESS_STEPS + 1)
        }
        return {min(total, mark) for mark in marks}

    @staticmethod
    def _log_progress(
        adapter: BaseStoreAdapter,
        processed: int,
        total: int,
        progress_marks: set[int],
    ) -> None:
        if processed in progress_marks:
            adapter.logger.info(
                "[%s] Progress: %s/%s",
                adapter.store_id,
                processed,
                total,
            )

    def _set_run_stats(
        self,
        store_id: str,
        start_time: datetime,
        discovered_count: int,
        parsed_count: int,
        error_count: int,
        confirmed_deals_count: int,
        skipped_count: int,
        failed_urls: list[str],
        error_snippet: str,
    ) -> None:
        self.last_stats = RunStats(
            store_id=store_id,
            start_time=start_time,
            discovered_count=discovered_count,
            parsed_count=parsed_count,
            error_count=error_count,
            confirmed_deals_count=confirmed_deals_count,
            skipped_count=skipped_count,
        )
        self.last_failed_urls = failed_urls
        self.last_error_snippet = error_snippet

    @staticmethod
    def _extract_blocked_url(message: str) -> str | None:
        prefix = f"{_BLOCKED_SIGNAL}:"
        if message.startswith(prefix):
            url = message[len(prefix):].strip()
            if url:
                return url
        return None
