from __future__ import annotations

import dealwatch.application.urls as url_module

from dealwatch.application.urls import normalize_url, resolve_store_for_url
from dealwatch.compare.matching import (
    build_candidate_key,
    build_candidate_snapshot,
    build_match_details,
    compute_match_score,
)
from dealwatch.stores.walmart.adapter import WalmartAdapter


def test_normalize_url_strips_query_and_fragment() -> None:
    normalized = normalize_url("https://www.sayweee.com/zh/product/demo/1?foo=bar#section")
    assert normalized == "https://www.sayweee.com/zh/product/demo/1"


def test_resolve_store_for_url_rejects_unknown_host() -> None:
    resolved = resolve_store_for_url("https://example.com/not-supported")
    assert resolved.supported is False
    assert resolved.error_code == "unsupported_store_host"


def test_resolve_store_for_url_marks_recognized_host_with_unsupported_path() -> None:
    resolved = resolve_store_for_url("https://www.target.com/c/grocery/-/N-5xt1a")
    assert resolved.supported is False
    assert resolved.store_key == "target"
    assert resolved.error_code == "unsupported_store_path"


def test_resolve_store_for_url_supports_ranch99_product_detail() -> None:
    resolved = resolve_store_for_url(
        "https://www.99ranch.com/product-details/1615424/8899/078895126389?foo=bar#frag"
    )
    assert resolved.supported is True
    assert resolved.store_key == "ranch99"
    assert resolved.product_url == "https://www.99ranch.com/product-details/1615424/8899/078895126389"


def test_resolve_store_for_url_supports_target_product_detail() -> None:
    resolved = resolve_store_for_url(
        "https://www.target.com/p/utz-ripples-original-potato-chips-7-75oz/-/A-13202943?foo=bar#frag"
    )
    assert resolved.supported is True
    assert resolved.store_key == "target"
    assert (
        resolved.product_url
        == "https://www.target.com/p/-/A-13202943"
    )


def test_resolve_store_for_url_supports_safeway_product_detail() -> None:
    resolved = resolve_store_for_url(
        "https://www.safeway.com/SHOP/PRODUCT-DETAILS.960127167.HTML?storeId=3132#details"
    )
    assert resolved.supported is True
    assert resolved.store_key == "safeway"
    assert resolved.product_url == "https://www.safeway.com/shop/product-details.960127167.html"


def test_resolve_store_for_url_supports_walmart_product_detail(monkeypatch) -> None:
    monkeypatch.setitem(url_module.STORE_REGISTRY, WalmartAdapter.store_id, WalmartAdapter)

    resolved = resolve_store_for_url(
        "https://www.walmart.com/ip/Great-Value-Whole-Vitamin-D-Milk-1-gal/10450117?athbdg=L1600#details"
    )

    assert resolved.supported is True
    assert resolved.store_key == "walmart"
    assert resolved.product_url == "https://www.walmart.com/ip/10450117"


def test_resolve_store_for_url_marks_walmart_host_with_unsupported_path(monkeypatch) -> None:
    monkeypatch.setitem(url_module.STORE_REGISTRY, WalmartAdapter.store_id, WalmartAdapter)

    resolved = resolve_store_for_url("https://www.walmart.com/browse/grocery/milk/976759_1071964")

    assert resolved.supported is False
    assert resolved.store_key == "walmart"
    assert resolved.error_code == "unsupported_store_path"


def test_compare_helpers_build_and_score_candidates() -> None:
    left = build_candidate_key("Noodles 500g spicy", brand="ACME", size_hint="500g")
    right = build_candidate_key("Spicy noodles 500g", brand="ACME", size_hint="500g")
    assert compute_match_score(left, right) > 80


def test_compare_helpers_build_match_details_with_brand_and_size() -> None:
    left = build_candidate_snapshot(
        "Utz Ripples Original Potato Chips 7.75oz",
        brand="Utz",
        size_hint="7.75oz",
        product_key="13202943",
    )
    right = build_candidate_snapshot(
        "Utz Original Ripples Potato Chips 7.75 oz",
        brand="Utz",
        size_hint="7.75 oz",
        product_key="13202943",
    )

    details = build_match_details(left, right)

    assert details["score"] > 90
    assert details["brand_signal"] == "match"
    assert details["size_signal"] == "match"
    assert details["product_key_signal"] == "same-product-key"
    assert details["why_like"]


def test_compare_helpers_preserve_integral_size_quantities() -> None:
    snapshot = build_candidate_snapshot(
        "Large Tortilla Chips 10 oz",
        brand="Casa",
        size_hint="10.0 oz",
        product_key="abc",
    )

    assert snapshot.size_hint == "10 oz"


def test_compare_helpers_preserve_gallon_size_quantities() -> None:
    snapshot = build_candidate_snapshot(
        "Great Value Whole Vitamin D Milk, 1 gal",
        brand="Great Value",
        size_hint="1 gallon",
        product_key="10450117",
    )

    assert snapshot.size_hint == "1 gal"


def test_compare_helpers_penalize_mismatched_brand_and_size() -> None:
    left = build_candidate_snapshot("Spicy Noodles 500g", brand="ACME", size_hint="500g")
    right = build_candidate_snapshot("Spicy Noodles 750g", brand="OTHER", size_hint="750g")

    details = build_match_details(left, right)

    assert details["brand_signal"] == "mismatch"
    assert details["size_signal"] == "mismatch"
    assert details["score"] < 80
    assert details["why_unlike"]
