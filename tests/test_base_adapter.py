import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from dealwatch.core.models import SkipReason
from dealwatch.core.models import Offer, PriceContext
from dealwatch.core.artifacts import ArtifactManager
from dealwatch.stores.base_adapter import BaseStoreAdapter, SkipParse, safe_parse
import dealwatch.stores as stores


class _DummyAdapter(BaseStoreAdapter):
    store_id = "dummy"
    base_url = "https://example.com"

    async def discover_deals(self) -> list[str]:
        return []

    async def parse_product(self, url: str):
        return None


@pytest.mark.asyncio
async def test_safe_parse_handles_exception() -> None:
    class _Adapter(_DummyAdapter):
        @safe_parse
        async def parse_product(self, url: str):
            raise RuntimeError("boom")

    adapter = _Adapter(client=object(), settings=object())
    result = await adapter.parse_product("https://example.com")
    assert result is None


@pytest.mark.asyncio
async def test_safe_parse_passthrough_skip() -> None:
    class _Adapter(_DummyAdapter):
        @safe_parse
        async def parse_product(self, url: str):
            raise SkipParse(SkipReason.OUT_OF_STOCK)

    adapter = _Adapter(client=object(), settings=object())
    with pytest.raises(SkipParse):
        await adapter.parse_product("https://example.com")


def test_base_adapter_repr_and_state_path() -> None:
    adapter = _DummyAdapter(client=object(), settings=object())
    assert "dummy" in repr(adapter)
    path = adapter._build_storage_state_path("90-001")
    assert path.name.startswith("storage_state_90001")
    default_path = adapter._build_storage_state_path("!!!")
    assert default_path.name == "storage_state_default.json"


def test_base_adapter_print_diagnostics(capsys) -> None:
    adapter = _DummyAdapter(client=object(), settings=object())

    class _Parser:
        last_debug = {"source": "unit", "price": "missing"}

    adapter._parser = _Parser()
    adapter._print_diagnostics(adapter)
    output = capsys.readouterr().out
    assert "Diagnostics" in output
    assert "source" in output


@pytest.mark.asyncio
async def test_base_adapter_test_adapter(monkeypatch, capsys) -> None:
    class _Client:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

    class _Adapter(BaseStoreAdapter):
        store_id = "dummy"
        base_url = "https://example.com"

        async def discover_deals(self) -> list[str]:
            return []

        async def parse_product(self, url: str):
            return Offer(
                store_id="dummy",
                product_key="p1",
                title="Test",
                url=url,
                price=1.0,
                original_price=None,
                fetch_at=datetime(2026, 1, 18, 12, 0, 0, tzinfo=timezone.utc),
                context=PriceContext(region="00000"),
                unit_price_info={},
            )

    monkeypatch.setattr("dealwatch.stores.base_adapter.PlaywrightClient", _Client)
    monkeypatch.setitem(stores.STORE_REGISTRY, "dummy", _Adapter)

    await BaseStoreAdapter.test_adapter("https://example.com/product")
    output = capsys.readouterr().out
    assert "Title" in output


@pytest.mark.asyncio
async def test_base_adapter_test_adapter_no_match(monkeypatch, capsys) -> None:
    monkeypatch.setitem(stores.STORE_REGISTRY, "dummy", _DummyAdapter)
    monkeypatch.setattr(stores, "STORE_REGISTRY", {})

    await BaseStoreAdapter.test_adapter("https://unknown.example.com/product")
    output = capsys.readouterr().out
    assert "No adapter matches" in output


@pytest.mark.asyncio
async def test_base_adapter_test_adapter_parse_none(monkeypatch, capsys) -> None:
    class _Client:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

    class _Adapter(_DummyAdapter):
        async def parse_product(self, url: str):
            return None

    monkeypatch.setattr("dealwatch.stores.base_adapter.PlaywrightClient", _Client)
    monkeypatch.setitem(stores.STORE_REGISTRY, "dummy", _Adapter)

    await BaseStoreAdapter.test_adapter("https://example.com/product")
    output = capsys.readouterr().out
    assert "parse_product returned None" in output


class _FakePage:
    def __init__(self, content: str) -> None:
        self._content = content
        self.screenshot_paths: list[str] = []

    async def content(self) -> str:
        return self._content

    async def inner_text(self, selector: str) -> str:
        return "body text"

    async def screenshot(self, path: str) -> None:
        Path(path).write_bytes(b"fake")
        self.screenshot_paths.append(path)


@pytest.mark.asyncio
async def test_base_adapter_capture_failed_page(tmp_path, monkeypatch) -> None:
    adapter = _DummyAdapter(client=object(), settings=object())
    page = _FakePage("<html><body>broken</body></html>")

    def _fake_run_dir(self) -> Path:
        return tmp_path

    monkeypatch.setattr(ArtifactManager, "get_run_dir", _fake_run_dir)

    await adapter._capture_failed_page(page, "https://example.com/p1", "parse_error")

    html_files = list((tmp_path / "failures").rglob("*.html"))
    meta_files = list((tmp_path / "failures").rglob("*.json"))
    screenshot_files = list((tmp_path / "failures").rglob("*.png"))
    text_files = list((tmp_path / "failures").rglob("*.txt"))
    index_json = tmp_path / "failures_index.ndjson"
    index_md = tmp_path / "failures_index.md"

    assert len(html_files) == 1
    assert len(meta_files) == 1
    assert len(screenshot_files) == 1
    assert len(text_files) == 1
    assert index_json.exists() is True
    assert index_md.exists() is True

    assert html_files[0].read_text(encoding="utf-8") == "<html><body>broken</body></html>"
    assert text_files[0].read_text(encoding="utf-8") == "body text"
    payload = json.loads(meta_files[0].read_text(encoding="utf-8"))
    assert payload["url"] == "https://example.com/p1"


@pytest.mark.asyncio
async def test_base_adapter_capture_failed_page_mkdir_failure(monkeypatch) -> None:
    adapter = _DummyAdapter(client=object(), settings=object())

    def _raise(*args, **kwargs):
        raise OSError("boom")

    monkeypatch.setattr(Path, "mkdir", _raise)
    page = _FakePage("<html></html>")

    await adapter._capture_failed_page(page, "https://example.com/p2", "reason")


@pytest.mark.asyncio
async def test_base_adapter_capture_failed_page_content_failure(tmp_path, monkeypatch) -> None:
    adapter = _DummyAdapter(client=object(), settings=object())
    def _fake_run_dir(self) -> Path:
        return tmp_path

    monkeypatch.setattr(ArtifactManager, "get_run_dir", _fake_run_dir)

    class _BadContentPage(_FakePage):
        async def content(self) -> str:
            raise OSError("no content")

    page = _BadContentPage("<html></html>")
    await adapter._capture_failed_page(page, "https://example.com/p3", "reason")

    assert list(tmp_path.rglob("*.json"))
    assert list(tmp_path.rglob("*.txt"))


@pytest.mark.asyncio
async def test_base_adapter_capture_failed_page_screenshot_failure(tmp_path, monkeypatch) -> None:
    adapter = _DummyAdapter(client=object(), settings=object())
    def _fake_run_dir(self) -> Path:
        return tmp_path

    monkeypatch.setattr(ArtifactManager, "get_run_dir", _fake_run_dir)

    class _BadScreenshotPage(_FakePage):
        async def screenshot(self, path: str) -> None:
            raise OSError("no screenshot")

    page = _BadScreenshotPage("<html></html>")
    await adapter._capture_failed_page(page, "https://example.com/p4", "reason")

    assert list(tmp_path.rglob("*.json"))


@pytest.mark.asyncio
async def test_base_adapter_capture_failed_page_meta_failure(monkeypatch, tmp_path) -> None:
    adapter = _DummyAdapter(client=object(), settings=object())
    def _fake_run_dir(self) -> Path:
        return tmp_path

    monkeypatch.setattr(ArtifactManager, "get_run_dir", _fake_run_dir)
    page = _FakePage("<html></html>")

    original_write_text = Path.write_text

    def _write_text(self, data, *args, **kwargs):
        if self.suffix == ".json":
            raise OSError("no meta")
        return original_write_text(self, data, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", _write_text)
    await adapter._capture_failed_page(page, "https://example.com/p5", "")

    assert adapter._sanitize_reason("") == "unknown"


@pytest.mark.asyncio
async def test_base_adapter_capture_failed_page_run_dir_failure(monkeypatch) -> None:
    adapter = _DummyAdapter(client=object(), settings=object())

    def _raise(self):
        raise OSError("no dir")

    monkeypatch.setattr(ArtifactManager, "get_run_dir", _raise)
    page = _FakePage("<html></html>")

    await adapter._capture_failed_page(page, "https://example.com/p6", "reason")


@pytest.mark.asyncio
async def test_base_adapter_capture_failed_page_index_failure(monkeypatch, tmp_path) -> None:
    adapter = _DummyAdapter(client=object(), settings=object())

    def _fake_run_dir(self) -> Path:
        return tmp_path

    monkeypatch.setattr(ArtifactManager, "get_run_dir", _fake_run_dir)
    page = _FakePage("<html></html>")

    original_open = Path.open

    def _open(self, *args, **kwargs):
        if self.name.startswith("failures_index."):
            raise OSError("no index")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", _open)
    await adapter._capture_failed_page(page, "https://example.com/p7", "reason")


@pytest.mark.asyncio
async def test_base_adapter_failure_dir_mkdir_failure(monkeypatch, tmp_path) -> None:
    adapter = _DummyAdapter(client=object(), settings=object())

    def _fake_run_dir(self) -> Path:
        return tmp_path

    monkeypatch.setattr(ArtifactManager, "get_run_dir", _fake_run_dir)
    original_mkdir = Path.mkdir

    def _mkdir(self, *args, **kwargs):
        if self.name == "dummy":
            raise OSError("boom")
        return original_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", _mkdir)
    page = _FakePage("<html></html>")
    await adapter._capture_failed_page(page, "https://example.com/p8", "reason")


@pytest.mark.asyncio
async def test_base_adapter_append_failure_index_outer_exception(tmp_path, monkeypatch) -> None:
    adapter = _DummyAdapter(client=object(), settings=object())

    class _BadLock:
        async def __aenter__(self):
            raise RuntimeError("boom")

        async def __aexit__(self, exc_type, exc, tb):
            return None

    monkeypatch.setattr(adapter, "_get_failure_index_lock", lambda: _BadLock())
    await adapter._append_failure_index(
        tmp_path,
        {
            "captured_at": "20260101_000000",
            "html_path": "a.html",
            "screenshot_path": "a.png",
            "reason": "boom",
            "url": "https://example.com",
        },
    )


def test_base_adapter_safe_rel_path() -> None:
    base = Path("/tmp/base")
    path = Path("/other/path/file.txt")
    rel = BaseStoreAdapter._safe_rel_path(path, base)
    assert rel == str(path)
