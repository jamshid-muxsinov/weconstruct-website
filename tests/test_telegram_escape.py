from src.services.telegram_service import _escape_markdown


def test_escape_markdown_escapes_special_characters():
    escaped = _escape_markdown("name_[test](ok)!")
    assert escaped == r"name\_\[test\]\(ok\)\!"
