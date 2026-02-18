from datetime import timedelta

from jose import jwt

from src.core.security import create_access_token, settings


def test_create_access_token_contains_subject():
    token = create_access_token({"sub": "tester"}, expires_delta=timedelta(minutes=5))
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert payload["sub"] == "tester"
    assert "exp" in payload
