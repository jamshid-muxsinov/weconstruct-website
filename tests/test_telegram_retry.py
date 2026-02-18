import asyncio

import httpx

from src.services import telegram_service


def test_send_new_lead_notification_retries_on_server_error(monkeypatch):
    calls = {"count": 0}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json):
            calls["count"] += 1
            status = 500 if calls["count"] == 1 else 200
            return httpx.Response(
                status_code=status,
                request=httpx.Request("POST", url),
                text="error" if status != 200 else "ok",
            )

    async def fake_sleep(_seconds):
        return None

    monkeypatch.setattr(telegram_service.settings, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(telegram_service.settings, "TELEGRAM_CHAT_ID", "chat")
    monkeypatch.setattr(telegram_service.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(telegram_service.asyncio, "sleep", fake_sleep)

    asyncio.run(
        telegram_service.send_new_lead_notification(
            {
                "source_text": "Новая заявка",
                "client_name": "Test",
                "phone": "+998900000000",
                "subject": "Demo",
            }
        )
    )

    assert calls["count"] == 2
