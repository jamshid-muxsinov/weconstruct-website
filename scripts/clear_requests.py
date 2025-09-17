# scripts/clear_requests.py
import asyncio
from sqlalchemy import delete

# Убедимся, что Python может найти наши модули из папки src
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

# --- ИСПРАВЛЕНИЕ ЗДЕСЬ ---
# Мы импортируем ВАШУ фабрику сессий из вашего проекта, а не из SQLAlchemy
from src.core.db import async_session_factory
# -------------------------

from src.models.shop_models import QuoteRequest, Task, StatusChangeLog, GoogleSheetLead

async def clear_all_requests_data():
    """
    Полностью очищает все заявки и связанные с ними данные.
    НЕ ТРОГАЕТ КОНТАКТЫ.
    """
    print("ВНИМАНИЕ! Этот скрипт безвозвратно удалит ВСЕ заявки, задачи,")
    print("логи смены статусов и записи об импорте из Google Sheets.")
    print("Таблица контактов затронута НЕ БУДЕТ.")
    
    confirmation = input('Для подтверждения введите "YES": ')
    
    if confirmation != "YES":
        print("Операция отменена.")
        return

    print("\nНачинаю удаление...")
    
    async with async_session_factory() as session:
        async with session.begin():
            # Удаляем в порядке зависимостей, чтобы избежать ошибок
            
            # 1. Записи об импорте
            result_gs = await session.execute(delete(GoogleSheetLead))
            print(f"- Удалено записей об импорте: {result_gs.rowcount}")
            
            # 2. Логи смены статусов
            result_logs = await session.execute(delete(StatusChangeLog))
            print(f"- Удалено логов смены статусов: {result_logs.rowcount}")

            # 3. Задачи
            result_tasks = await session.execute(delete(Task))
            print(f"- Удалено задач: {result_tasks.rowcount}")
            
            # 4. Сами заявки
            result_reqs = await session.execute(delete(QuoteRequest))
            print(f"- Удалено заявок: {result_reqs.rowcount}")

        await session.commit()
    
    print("\nОчистка успешно завершена!")

if __name__ == "__main__":
    asyncio.run(clear_all_requests_data())