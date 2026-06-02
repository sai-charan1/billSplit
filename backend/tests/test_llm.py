from app.gemini_client import is_valid_key_format


def test_valid_legacy_key_format() -> None:
    assert is_valid_key_format("AIzaSyExampleKey123")


def test_valid_new_key_format() -> None:
    assert is_valid_key_format("AQ.Ab8RN6ExampleKey")


def test_invalid_key_format() -> None:
    assert not is_valid_key_format("yAQ.invalid")
    assert not is_valid_key_format("")
