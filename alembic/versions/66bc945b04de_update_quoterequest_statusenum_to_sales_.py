"""Update QuoteRequest StatusEnum to sales funnel stages

Revision ID: 66bc945b04de
Revises: 3efeb482c524
Create Date: 2025-09-04 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '66bc945b04de'
down_revision: Union[str, None] = '3efeb482c524'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Определяем новый тип ENUM с уникальным именем, чтобы не конфликтовать с Product
new_quoterequest_enum = postgresql.ENUM(
    'imported', 'qualification', 'contacted', 'proposal', 'negotiation', 'closed', 'archived',
    name='quoterequest_status_enum'
)

# Определяем старый тип ENUM для отката
old_shared_enum = postgresql.ENUM(
    'new', 'in_progress', 'completed', 'cancelled',
    name='statusenum'
)


def upgrade() -> None:
    # Шаг 1: Создаем наш НОВЫЙ, отдельный тип для заявок
    new_quoterequest_enum.create(op.get_bind(), checkfirst=True)

    # Шаг 2: Меняем тип колонки status в 'shop_quoterequest', конвертируя старые значения в новые
    op.execute("""
        ALTER TABLE shop_quoterequest
        ALTER COLUMN status TYPE quoterequest_status_enum
        USING (CASE
            WHEN status = 'new' THEN 'imported'::quoterequest_status_enum
            WHEN status = 'in_progress' THEN 'qualification'::quoterequest_status_enum
            WHEN status = 'completed' THEN 'closed'::quoterequest_status_enum
            WHEN status = 'cancelled' THEN 'archived'::quoterequest_status_enum
            ELSE 'imported'::quoterequest_status_enum
        END)
    """)

    # Шаг 3: Делаем то же самое для таблицы логов (old_status)
    op.execute("""
        ALTER TABLE shop_statuschangelog
        ALTER COLUMN old_status TYPE quoterequest_status_enum
        USING (CASE
            WHEN old_status = 'new' THEN 'imported'::quoterequest_status_enum
            WHEN old_status = 'in_progress' THEN 'qualification'::quoterequest_status_enum
            WHEN old_status = 'completed' THEN 'closed'::quoterequest_status_enum
            WHEN old_status = 'cancelled' THEN 'archived'::quoterequest_status_enum
            ELSE 'imported'::quoterequest_status_enum
        END)
    """)

    # Шаг 4: И для таблицы логов (new_status)
    op.execute("""
        ALTER TABLE shop_statuschangelog
        ALTER COLUMN new_status TYPE quoterequest_status_enum
        USING (CASE
            WHEN new_status = 'new' THEN 'imported'::quoterequest_status_enum
            WHEN new_status = 'in_progress' THEN 'qualification'::quoterequest_status_enum
            WHEN new_status = 'completed' THEN 'closed'::quoterequest_status_enum
            WHEN new_status = 'cancelled' THEN 'archived'::quoterequest_status_enum
            ELSE 'imported'::quoterequest_status_enum
        END)
    """)
    # Мы НЕ удаляем и НЕ переименовываем старый тип 'statusenum', так как он нужен для таблицы Product.


def downgrade() -> None:
    # При откате мы делаем все наоборот: меняем тип колонок обратно на старый ОБЩИЙ тип.

    # Шаг 1: Меняем тип колонки status в 'shop_quoterequest' обратно на 'statusenum'
    op.execute("""
        ALTER TABLE shop_quoterequest
        ALTER COLUMN status TYPE statusenum
        USING (CASE
            WHEN status = 'imported' THEN 'new'::statusenum
            WHEN status = 'qualification' THEN 'in_progress'::statusenum
            WHEN status = 'closed' THEN 'completed'::statusenum
            WHEN status = 'archived' THEN 'cancelled'::statusenum
            ELSE 'new'::statusenum
        END)
    """)

    # Шаг 2: Меняем тип колонки old_status в 'shop_statuschangelog' обратно на 'statusenum'
    op.execute("""
        ALTER TABLE shop_statuschangelog
        ALTER COLUMN old_status TYPE statusenum
        USING (CASE
            WHEN old_status = 'imported' THEN 'new'::statusenum
            WHEN old_status = 'qualification' THEN 'in_progress'::statusenum
            WHEN old_status = 'closed' THEN 'completed'::statusenum
            WHEN old_status = 'archived' THEN 'cancelled'::statusenum
            ELSE 'new'::statusenum
        END)
    """)

    # Шаг 3: Меняем тип колонки new_status в 'shop_statuschangelog' обратно на 'statusenum'
    op.execute("""
        ALTER TABLE shop_statuschangelog
        ALTER COLUMN new_status TYPE statusenum
        USING (CASE
            WHEN new_status = 'imported' THEN 'new'::statusenum
            WHEN new_status = 'qualification' THEN 'in_progress'::statusenum
            WHEN new_status = 'closed' THEN 'completed'::statusenum
            WHEN new_status = 'archived' THEN 'cancelled'::statusenum
            ELSE 'new'::statusenum
        END)
    """)

    # Шаг 4: Теперь, когда наш новый тип 'quoterequest_status_enum' больше никем не используется, его можно безопасно удалить.
    new_quoterequest_enum.drop(op.get_bind(), checkfirst=False)