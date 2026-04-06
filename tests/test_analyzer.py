import json
import types
import builtins

import pytest

from dealwatch.core.ai_analyzer import AIAnalyzer
from dealwatch.infra.config import Settings


def test_ai_normalize_model_name() -> None:
    settings = Settings()
    analyzer = AIAnalyzer(settings)
    assert analyzer._normalize_model_name("") == "openai/gpt-4o-mini"
    assert analyzer._normalize_model_name("gpt-4o-mini") == "openai/gpt-4o-mini"
    assert analyzer._normalize_model_name("openai/gpt-4o-mini") == "openai/gpt-4o-mini"


def test_ai_parse_plan_valid_and_invalid() -> None:
    settings = Settings()
    analyzer = AIAnalyzer(settings)
    allowed = {"weee:1"}
    good = json.dumps(
        {
            "categories": [
                {"category": "fruits", "items": [{"id": "weee:1", "comment": "ok"}]}
            ],
            "top_picks": [{"id": "weee:1", "comment": "top"}],
        }
    )
    plan, reason = analyzer._parse_ai_plan(good, allowed)
    assert reason == ""
    assert plan is not None
    assert plan["categories"][0]["category"] == "fruits"

    bad = "not-json"
    plan, reason = analyzer._parse_ai_plan(bad, allowed)
    assert plan is None
    assert reason == "invalid_json"


def test_ai_render_html_from_plan() -> None:
    settings = Settings()
    analyzer = AIAnalyzer(settings)
    deals = [
        {
            "offer": {
                "deal_id": "weee:1",
                "store_id": "weee",
                "product_key": "1",
                "title": "Test Item",
                "price": 1.99,
                "original_price": 2.99,
                "url": "https://example.com",
            },
            "drop_pct": 33.0,
        }
    ]
    plan = {
        "categories": [
            {"category": "snacks", "items": [{"id": "weee:1", "comment": "nice"}]}
        ],
        "top_picks": [],
    }
    html = analyzer._render_html_from_plan(plan, deals)
    assert "<table>" in html
    assert "Test Item" in html


@pytest.mark.asyncio
async def test_ai_analyze_invalid_json(tmp_path) -> None:
    settings = Settings(USE_LLM=False)
    analyzer = AIAnalyzer(settings)
    path = tmp_path / "bad.json"
    path.write_text("{not-json", encoding="utf-8")
    html = await analyzer.analyze(path)
    assert "table" in html


@pytest.mark.asyncio
async def test_ai_analyze_llm_disabled(tmp_path) -> None:
    settings = Settings(USE_LLM=False)
    analyzer = AIAnalyzer(settings)
    path = tmp_path / "deals.json"
    path.write_text(json.dumps({"deals": []}), encoding="utf-8")
    html = await analyzer.analyze(path)
    assert "AI analysis is disabled" in html


@pytest.mark.asyncio
async def test_ai_analyze_deals_not_list(tmp_path) -> None:
    settings = Settings(USE_LLM=False)
    analyzer = AIAnalyzer(settings)
    path = tmp_path / "deals.json"
    path.write_text(json.dumps({"deals": "bad"}), encoding="utf-8")
    html = await analyzer.analyze(path)
    assert "table" in html


@pytest.mark.asyncio
async def test_ai_analyze_success_first_try(tmp_path, monkeypatch) -> None:
    settings = Settings(USE_LLM=True, LLM_API_KEY="sk-test")
    analyzer = AIAnalyzer(settings)
    path = tmp_path / "deals.json"
    path.write_text(
        json.dumps(
            {
                "deals": [
                    {
                        "offer": {
                            "deal_id": "x",
                            "store_id": "weee",
                            "product_key": "x",
                            "title": "Item",
                            "price": 1.0,
                            "original_price": 2.0,
                            "url": "https://example.com",
                        },
                        "drop_pct": 50.0,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    async def _fake_call(self, *args, **kwargs):
        return json.dumps({"categories": [], "top_picks": [{"id": "x", "comment": ""}]})

    monkeypatch.setattr(AIAnalyzer, "_call_dspy", _fake_call)
    html = await analyzer.analyze(path)
    assert "<table>" in html


@pytest.mark.asyncio
async def test_ai_analyze_exception_fallback(tmp_path, monkeypatch) -> None:
    settings = Settings(USE_LLM=True, LLM_API_KEY="sk-test")
    analyzer = AIAnalyzer(settings)
    path = tmp_path / "deals.json"
    path.write_text(json.dumps({"deals": []}), encoding="utf-8")

    async def _boom(self, *args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(AIAnalyzer, "_call_dspy", _boom)
    html = await analyzer.analyze(path)
    assert "Falling back" in html


@pytest.mark.asyncio
async def test_ai_call_dspy_with_fake_module(monkeypatch) -> None:
    settings = Settings(USE_LLM=True, LLM_API_KEY="sk-test")
    analyzer = AIAnalyzer(settings)

    fake_output = json.dumps(
        {
            "categories": [{"category": "snacks", "items": [{"id": "weee:1", "comment": "ok"}]}],
            "top_picks": [],
        }
    )

    class _FakePredict:
        def __init__(self, signature):
            self.signature = signature

        async def acall(self, system_prompt: str, payload: str):
            return types.SimpleNamespace(output=fake_output)

    class _FakeLM:
        def __init__(self, model: str, api_key: str, temperature: float) -> None:
            self.model = model
            self.api_key = api_key
            self.temperature = temperature

    fake_module = types.SimpleNamespace(
        LM=_FakeLM,
        configure=lambda **kwargs: None,
        Predict=_FakePredict,
        Signature=type("Signature", (), {}),
        InputField=lambda *args, **kwargs: None,
        OutputField=lambda *args, **kwargs: None,
    )

    monkeypatch.setitem(__import__("sys").modules, "dspy", fake_module)

    output = await analyzer._call_dspy({"deals": []}, temperature=0.1)
    assert output == fake_output


@pytest.mark.asyncio
async def test_ai_call_dspy_missing_module(monkeypatch) -> None:
    settings = Settings(USE_LLM=True, LLM_API_KEY="sk-test")
    analyzer = AIAnalyzer(settings)

    original_import = builtins.__import__

    def _import(name, *args, **kwargs):
        if name == "dspy":
            raise ImportError("missing")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _import)

    with pytest.raises(RuntimeError):
        await analyzer._call_dspy({}, temperature=0.1)


@pytest.mark.asyncio
async def test_ai_call_dspy_errors() -> None:
    disabled = AIAnalyzer(Settings(USE_LLM=False))
    with pytest.raises(RuntimeError):
        await disabled._call_dspy({}, temperature=0.1)

    missing_key = AIAnalyzer(Settings(USE_LLM=True, LLM_API_KEY=""))
    with pytest.raises(RuntimeError):
        await missing_key._call_dspy({}, temperature=0.1)


@pytest.mark.asyncio
async def test_ai_analyze_retry_then_success(tmp_path, monkeypatch) -> None:
    settings = Settings(USE_LLM=True, LLM_API_KEY="sk-test")
    analyzer = AIAnalyzer(settings)

    deals_payload = {
        "run_time": "2026-01-01T00:00:00Z",
        "total_checked": 1,
        "confirmed_count": 1,
        "deals": [
            {
                "offer": {
                    "deal_id": "weee:1",
                    "store_id": "weee",
                    "product_key": "1",
                    "title": "Test Item",
                    "price": 1.99,
                    "original_price": 2.99,
                    "url": "https://example.com",
                },
                "drop_pct": 33.0,
            }
        ],
    }
    path = tmp_path / "deals.json"
    path.write_text(json.dumps(deals_payload), encoding="utf-8")

    responses = iter(["not-json", json.dumps(
        {
            "categories": [
                {"category": "snacks", "items": [{"id": "weee:1", "comment": "ok"}]}
            ],
            "top_picks": [],
        }
    )])

    async def _fake_call(self, *args, **kwargs):
        return next(responses)

    monkeypatch.setattr(AIAnalyzer, "_call_dspy", _fake_call)

    html = await analyzer.analyze(path)
    assert "<table>" in html


def test_ai_parse_plan_edge_cases() -> None:
    analyzer = AIAnalyzer(Settings())
    allowed = {"id-1"}

    plan, reason = analyzer._parse_ai_plan("", allowed)
    assert plan is None
    assert reason == "empty_output"

    plan, reason = analyzer._parse_ai_plan("{}", allowed)
    assert plan is None
    assert reason == "json_key_type_invalid"

    plan, reason = analyzer._parse_ai_plan(json.dumps({"categories": [], "top_picks": []}), allowed)
    assert plan is None
    assert reason == "empty_plan"

    plan, reason = analyzer._parse_ai_plan(json.dumps([]), allowed)
    assert plan is None
    assert reason == "json_not_object"


def test_ai_filter_items_and_allowed_ids() -> None:
    analyzer = AIAnalyzer(Settings())
    deals = [
        {"offer": {"store_id": "weee", "product_key": "1", "deal_id": "weee:1"}},
        {"offer": {"store_id": "weee", "product_key": "2"}},
        {"offer": {"product_key": "2"}},
        "bad",
    ]
    allowed = analyzer._build_allowed_ids(deals)
    assert "weee:1" in allowed

    items = [{"id": "weee:1", "comment": "ok"}, {"id": "missing"}]
    filtered = analyzer._filter_items(items, allowed)
    assert len(filtered) == 1

    product_only = [{"offer": {"product_key": "solo"}}]
    allowed = analyzer._build_allowed_ids(product_only)
    assert "solo" in allowed


def test_ai_trim_deals_invalid_drop_pct() -> None:
    analyzer = AIAnalyzer(Settings())
    deals = [{"drop_pct": "bad"}, {"drop_pct": 10}]
    trimmed = analyzer._trim_deals(deals)
    assert trimmed[0]["drop_pct"] == 10


def test_ai_trim_deals_over_limit() -> None:
    analyzer = AIAnalyzer(Settings())
    deals = [{"drop_pct": i} for i in range(100)]
    trimmed = analyzer._trim_deals(deals)
    assert len(trimmed) == 50


def test_ai_render_plan_empty_sections() -> None:
    analyzer = AIAnalyzer(Settings())
    html = analyzer._render_html_from_plan({"categories": [], "top_picks": []}, [])
    assert "No usable AI-generated recommendations were produced" in html


def test_ai_render_rows_skips_missing() -> None:
    analyzer = AIAnalyzer(Settings())
    rows = analyzer._render_rows([{"comment": "no id"}], {})
    assert rows == ""


def test_ai_escape_text_none() -> None:
    analyzer = AIAnalyzer(Settings())
    assert analyzer._escape_text(None) == ""
