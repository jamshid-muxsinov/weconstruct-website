from src.pages.admin import auth


def test_access_cookie_secure_flag_when_debug_enabled(monkeypatch):
    monkeypatch.setattr(auth.settings, "DEBUG", True)
    assert auth.get_access_cookie_secure_flag() is False


def test_access_cookie_secure_flag_when_debug_disabled(monkeypatch):
    monkeypatch.setattr(auth.settings, "DEBUG", False)
    assert auth.get_access_cookie_secure_flag() is True


def test_access_cookie_secure_flag_prefers_explicit_setting(monkeypatch):
    monkeypatch.setattr(auth.settings, "DEBUG", True)
    monkeypatch.setattr(auth.settings, "COOKIE_SECURE", True)
    assert auth.get_access_cookie_secure_flag() is True
