from app.llm import COMBINED_PROMPT, _fill_prompt


def test_combined_prompt_does_not_raise_on_json_braces() -> None:
    filled = _fill_prompt(
        COMBINED_PROMPT,
        description="Four of us: Aman, Priya. Priya paid.",
    )
    assert '"receipt"' in filled
    assert "Four of us: Aman, Priya" in filled
    assert "{description}" not in filled
