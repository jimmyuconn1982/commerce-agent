from commerce_agent.search_parser import SearchParser


def test_search_parser_extracts_price_category_and_sort() -> None:
    parsed = SearchParser().parse(
        "red electronics under 100 cheapest",
        known_categories={"electronics", "furniture"},
    )

    assert parsed.category_hints == ["electronics"]
    assert parsed.attribute_hints == ["red"]
    assert parsed.max_price == 100.0
    assert parsed.min_price is None
    assert parsed.sort == "price_asc"


def test_search_parser_keeps_remaining_query() -> None:
    parsed = SearchParser().parse("compact office keyboard")
    assert parsed.remaining_query == "compact office keyboard"


def test_search_parser_does_not_hardcode_domain_expansion() -> None:
    parsed = SearchParser().parse("产品列表中有哪几种食物,可以炒菜用的")
    assert parsed.remaining_query == "产品列表中有哪几种食物 可以炒菜用的"
