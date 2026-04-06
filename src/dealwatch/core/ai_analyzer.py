from __future__ import annotations

import html
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, List

from dealwatch.infra.config import Settings


#########################################################
# Constants
#########################################################
_DEFAULT_MODEL: Final[str] = "gpt-4o-mini"
_MAX_ITEMS: Final[int] = 50
_TOP_KEEP: Final[int] = 20
_DEFAULT_TEMPERATURE: Final[float] = 0.4
_RETRY_TEMPERATURE: Final[float] = 0.2



#########################################################
# Analyzer
#########################################################
@dataclass(slots=True)
class AIAnalyzer:
    settings: Settings
    model: str = _DEFAULT_MODEL
    output_format: str = "json"
    logger: logging.Logger = field(init=False, repr=False)

    _SYSTEM_PROMPT: Final[str] = (
        "You are a precise, witty, and demanding grocery merchandising specialist.\n"
        "Task: read the deal JSON payload, group offers into categories, and recommend top picks.\n"
        "Hard rules:\n"
        "1) Never alter any original price numbers, including discount percentages.\n"
        "2) Output JSON only. Do not emit HTML or free-form prose.\n"
        "3) The JSON must contain exactly two top-level keys: categories and top_picks.\n"
        "4) Each categories entry must contain category and items.\n"
        "5) Each item may contain only id and comment. The id must use offer.deal_id from the original payload (store_id:product_key).\n"
        "6) top_picks may contain at most 3 entries, and each entry may contain only id and comment.\n"
        "7) Do not output prices, links, inventory counts, or URLs. The application fills those fields from the original data by id.\n"
        "8) If a category has no items, omit that category.\n"
        "9) Example categories include produce, meat, seafood, frozen, snacks, dairy, pantry, staples, beverages, and kitchen goods.\n"
    )

    def __post_init__(self) -> None:
        self.logger = logging.getLogger(__name__)

    async def analyze(self, deals_json_path: Path) -> str:
        try:
            raw = deals_json_path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except Exception as exc:
            self.logger.exception("Failed to load deals JSON: %s", exc)
            return self._fallback_html(
                [],
                "Failed to read the deals payload. Falling back to the basic table view.",
            )

        deals = data.get("deals") if isinstance(data, dict) else None
        if not isinstance(deals, list):
            deals = []

        trimmed = self._trim_deals(deals)

        # Check if LLM is enabled
        if not self.settings.USE_LLM:
            self.logger.info("USE_LLM is disabled, using fallback table mode")
            return self._fallback_html(
                trimmed,
                "AI analysis is disabled. Falling back to the basic table view.",
            )

        prompt_payload = {
            "run_time": data.get("run_time"),
            "total_checked": data.get("total_checked"),
            "confirmed_count": data.get("confirmed_count"),
            "deals": trimmed,
        }

        allowed_ids = self._build_allowed_ids(trimmed)

        try:
            response_text = await self._call_dspy(
                prompt_payload,
                temperature=_DEFAULT_TEMPERATURE,
            )
            plan, reason = self._parse_ai_plan(response_text, allowed_ids)
            if plan is not None:
                return self._render_html_from_plan(plan, trimmed)
            self.logger.warning("AI plan validation failed: %s", reason)

            response_text = await self._call_dspy(
                prompt_payload,
                temperature=_RETRY_TEMPERATURE,
            )
            plan, reason = self._parse_ai_plan(response_text, allowed_ids)
            if plan is not None:
                return self._render_html_from_plan(plan, trimmed)
            self.logger.warning("AI plan validation retry failed: %s", reason)
        except Exception as exc:
            self.logger.exception("AI analyze failed: %s", exc)

        return self._fallback_html(
            trimmed,
            "AI output validation failed. Falling back to the basic table view.",
        )

    #########################################################
    # DSPy Call
    #########################################################
    async def _call_dspy(self, payload: dict, temperature: float) -> str:
        if not self.settings.USE_LLM:
            raise RuntimeError("USE_LLM is disabled")
        api_key = self.settings.LLM_API_KEY.get_secret_value()
        if not api_key:
            raise RuntimeError("LLM_API_KEY is empty")

        try:
            import dspy
        except ImportError as exc:
            raise RuntimeError("dspy is not installed") from exc

        model = self._normalize_model_name(self.model)
        lm = dspy.LM(
            model,
            api_key=api_key,
            temperature=float(temperature),
        )
        dspy.configure(lm=lm)

        payload_text = json.dumps(payload, ensure_ascii=False)
        predictor = self._build_predictor(dspy)
        result = await predictor.acall(
            system_prompt=self._SYSTEM_PROMPT,
            payload=payload_text,
        )

        output = getattr(result, "output", None)
        if isinstance(output, str):
            return output.strip()
        if output is None:
            return ""
        return str(output).strip()

    #########################################################
    # Helpers
    #########################################################
    @staticmethod
    def _normalize_model_name(model: str) -> str:
        raw = str(model).strip()
        if not raw:
            return "openai/gpt-4o-mini"
        if "/" not in raw:
            return f"openai/{raw}"
        return raw

    @staticmethod
    def _build_predictor(dspy_module):
        class DigestSignature(dspy_module.Signature):
            system_prompt: str = dspy_module.InputField()
            payload: str = dspy_module.InputField()
            output: str = dspy_module.OutputField()

        return dspy_module.Predict(DigestSignature)

    def _parse_ai_plan(
        self,
        text: str | None,
        allowed_ids: set[str],
    ) -> tuple[dict | None, str]:
        if not text:
            return None, "empty_output"

        raw = str(text).strip()
        if not raw:
            return None, "empty_output"

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None, "invalid_json"

        if not isinstance(data, dict):
            return None, "json_not_object"

        categories = data.get("categories")
        top_picks = data.get("top_picks")
        if not isinstance(categories, list) or not isinstance(top_picks, list):
            return None, "json_key_type_invalid"

        parsed_categories: list[dict] = []
        for entry in categories:
            if not isinstance(entry, dict):
                continue
            category = str(entry.get("category", "")).strip()
            items = entry.get("items")
            if not category or not isinstance(items, list):
                continue
            filtered_items = self._filter_items(items, allowed_ids)
            if filtered_items:
                parsed_categories.append(
                    {
                        "category": category,
                        "items": filtered_items,
                    }
                )

        filtered_top = self._filter_items(top_picks, allowed_ids)[:3]

        if not parsed_categories and not filtered_top:
            return None, "empty_plan"

        return {
            "categories": parsed_categories,
            "top_picks": filtered_top,
        }, ""

    @staticmethod
    def _filter_items(items: list[object], allowed_ids: set[str]) -> list[dict]:
        filtered: list[dict] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            raw_id = str(item.get("id", "")).strip()
            if not raw_id or raw_id not in allowed_ids:
                continue
            comment = str(item.get("comment", "")).strip()
            filtered.append({"id": raw_id, "comment": comment})
        return filtered

    @staticmethod
    def _build_allowed_ids(deals: List[dict]) -> set[str]:
        allowed: set[str] = set()
        product_key_counts: dict[str, int] = {}
        for item in deals:
            offer = item.get("offer") if isinstance(item, dict) else None
            if not isinstance(offer, dict):
                continue
            deal_id = AIAnalyzer._extract_deal_id_from_offer(offer)
            if deal_id:
                allowed.add(deal_id)
            product_key = offer.get("product_key")
            if product_key:
                key = str(product_key).strip()
                if key:
                    product_key_counts[key] = product_key_counts.get(key, 0) + 1

        for key, count in product_key_counts.items():
            if count == 1:
                allowed.add(key)
        return allowed

    @staticmethod
    def _extract_deal_id_from_offer(offer: dict) -> str | None:
        raw_id = offer.get("deal_id")
        if raw_id:
            return str(raw_id).strip()

        store_id = offer.get("store_id")
        product_key = offer.get("product_key")
        if store_id and product_key:
            return f"{store_id}:{product_key}".strip()

        if product_key:
            return str(product_key).strip()

        return None

    @staticmethod
    def _render_html_from_plan(plan: dict, deals: List[dict]) -> str:
        deal_map: dict[str, dict] = {}
        product_key_counts: dict[str, int] = {}
        for item in deals:
            if not isinstance(item, dict):
                continue
            offer = item.get("offer")
            if not isinstance(offer, dict):
                continue
            deal_id = AIAnalyzer._extract_deal_id_from_offer(offer)
            if deal_id:
                deal_map[deal_id] = item
            product_key = offer.get("product_key")
            if product_key:
                key = str(product_key).strip()
                if key:
                    product_key_counts[key] = product_key_counts.get(key, 0) + 1

        for key, count in product_key_counts.items():
            if count == 1:
                for item in deals:
                    offer = item.get("offer") if isinstance(item, dict) else None
                    if not isinstance(offer, dict):
                        continue
                    if str(offer.get("product_key", "")).strip() == key:
                        deal_map[key] = item
                        break

        sections: list[str] = []

        top_picks = plan.get("top_picks", [])
        if isinstance(top_picks, list) and top_picks:
            rows = AIAnalyzer._render_rows(top_picks, deal_map)
            if rows:
                sections.append(
                    "<div>"
                    "<div>Top picks</div>"
                    "<table>"
                    "<thead>"
                    "<tr>"
                    "<th>Item</th>"
                    "<th>Current price</th>"
                    "<th>Original price</th>"
                    "<th>Drop (%)</th>"
                    "<th>Comment</th>"
                    "<th>URL</th>"
                    "</tr>"
                    "</thead>"
                    f"<tbody>{rows}</tbody>"
                    "</table>"
                    "</div>"
                )

        categories = plan.get("categories", [])
        if isinstance(categories, list):
            for entry in categories:
                if not isinstance(entry, dict):
                    continue
                category = AIAnalyzer._escape_text(entry.get("category", "")).strip()
                items = entry.get("items", [])
                if not category or not isinstance(items, list):
                    continue
                rows = AIAnalyzer._render_rows(items, deal_map)
                if not rows:
                    continue
                sections.append(
                    "<div>"
                    f"<div>{category}</div>"
                    "<table>"
                    "<thead>"
                    "<tr>"
                    "<th>Item</th>"
                    "<th>Current price</th>"
                    "<th>Original price</th>"
                    "<th>Drop (%)</th>"
                    "<th>Comment</th>"
                    "<th>URL</th>"
                    "</tr>"
                    "</thead>"
                    f"<tbody>{rows}</tbody>"
                    "</table>"
                    "</div>"
                )

        if not sections:
            return AIAnalyzer._fallback_html(
                deals, "No usable AI-generated recommendations were produced."
            )

        return "".join(sections)

    @staticmethod
    def _render_rows(items: list[dict], deal_map: dict[str, dict]) -> str:
        rows: list[str] = []
        for item in items:
            raw_id = str(item.get("id", "")).strip()
            if not raw_id:
                continue
            deal = deal_map.get(raw_id)
            if not deal:
                continue
            offer = deal.get("offer", {})
            title = AIAnalyzer._escape_text(offer.get("title", ""))
            price = AIAnalyzer._escape_text(offer.get("price", ""))
            original_value = offer.get("original_price", "")
            if original_value is None:
                original_value = ""
            original = AIAnalyzer._escape_text(original_value)
            drop_pct = AIAnalyzer._escape_text(deal.get("drop_pct", ""))
            url = AIAnalyzer._escape_text(offer.get("url", ""))
            comment = AIAnalyzer._escape_text(item.get("comment", ""))

            rows.append(
                "<tr>"
                f"<td>{title}</td>"
                f"<td>{price}</td>"
                f"<td>{original}</td>"
                f"<td>{drop_pct}</td>"
                f"<td>{comment}</td>"
                f"<td>{url}</td>"
                "</tr>"
            )

        return "".join(rows)

    @staticmethod
    def _trim_deals(deals: List[dict]) -> List[dict]:
        def _drop_pct(item: dict) -> float:
            try:
                return float(item.get("drop_pct", 0))
            except (TypeError, ValueError):
                return 0.0

        normalized = [item for item in deals if isinstance(item, dict)]
        sorted_deals = sorted(normalized, key=_drop_pct, reverse=True)
        if len(sorted_deals) <= _MAX_ITEMS:
            return sorted_deals

        head = sorted_deals[:_TOP_KEEP]
        tail = sorted_deals[_TOP_KEEP:_MAX_ITEMS]
        return head + tail

    @staticmethod
    def _fallback_html(deals: List[dict], note: str) -> str:
        safe_note = AIAnalyzer._escape_text(note)
        rows = []
        for item in deals[:20]:
            offer = item.get("offer", {})
            title = AIAnalyzer._escape_text(offer.get("title", ""))
            price = AIAnalyzer._escape_text(offer.get("price", ""))
            drop_pct = AIAnalyzer._escape_text(item.get("drop_pct", ""))
            url = AIAnalyzer._escape_text(offer.get("url", ""))
            rows.append(
                "<tr>"
                f"<td>{title}</td>"
                f"<td>{price}</td>"
                f"<td>{drop_pct}</td>"
                f"<td>{url}</td>"
                "</tr>"
            )

        table_rows = "".join(rows)
        return (
            "<div>"
            f"<div>{safe_note}</div>"
            "<table>"
            "<thead>"
            "<tr>"
            "<th>Item</th>"
            "<th>Current price</th>"
            "<th>Drop (%)</th>"
            "<th>URL</th>"
            "</tr>"
            "</thead>"
            f"<tbody>{table_rows}</tbody>"
            "</table>"
            "</div>"
        )

    @staticmethod
    def _escape_text(value: object) -> str:
        if value is None:
            return ""
        return html.escape(str(value), quote=True)
