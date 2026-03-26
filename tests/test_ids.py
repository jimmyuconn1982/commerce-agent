from commerce_agent.ids import SnowflakeLikeIdGenerator


def test_snowflake_like_generator_stable_ids_repeat() -> None:
    generator = SnowflakeLikeIdGenerator()
    first = generator.stable("public_product", "dummyjson:1")
    second = generator.stable("public_product", "dummyjson:1")

    assert first == second
    assert first > 0


def test_snowflake_like_generator_separates_entities() -> None:
    generator = SnowflakeLikeIdGenerator()
    product_id = generator.stable("public_product", "dummyjson:1")
    media_id = generator.stable("public_media", "dummyjson:1")

    assert product_id != media_id


def test_snowflake_like_generator_next_advances() -> None:
    generator = SnowflakeLikeIdGenerator()
    first = generator.next("tiny_offer")
    second = generator.next("tiny_offer")

    assert second > first
