# scripts/clear_requests.py
import asyncio
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_session_factory

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

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
            result_gs = await session.execute(delete(GoogleSheetLead))
            print(f"- Удалено записей об импорте: {result_gs.rowcount}")
            
            result_logs = await session.execute(delete(StatusChangeLog))
            print(f"- Удалено логов смены статусов: {result_logs.rowcount}")

            result_tasks = await session.execute(delete(Task))
            print(f"- Удалено задач: {result_tasks.rowcount}")
            
            result_reqs = await session.execute(delete(QuoteRequest))
            print(f"- Удалено заявок: {result_reqs.rowcount}")

        await session.commit()
    
    print("\nОчистка успешно завершена!")

if __name__ == "__main__":
    asyncio.run(clear_all_requests_data())