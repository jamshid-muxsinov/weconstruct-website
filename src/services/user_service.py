# src/services/user_service.py

import logging
import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError

from src.models.shop_models import User, RegistrationInvite, UserRole
from src.core.password import verify_password, get_password_hash
from src.schemas.user_schemas import UserCreate
from src.core.config import get_settings

log = logging.getLogger(__name__)
settings = get_settings()

async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    result = await db.execute(select(User).filter(User.username == username))
    return result.scalars().first()

async def authenticate_user(db: AsyncSession, username: str, password: str) -> Optional[User]:
    user = await get_user_by_username(db, username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user

async def change_user_password(db: AsyncSession, user: User, old_password: str, new_password: str) -> bool:
    if not verify_password(old_password, user.hashed_password):
        return False
    
    user.hashed_password = get_password_hash(new_password)
    db.add(user)
    await db.commit()
    return True

async def create_invite(db: AsyncSession, note: str, creator_id: int) -> RegistrationInvite:
    new_invite = RegistrationInvite(note=note, created_by_id=creator_id)
    db.add(new_invite)
    await db.commit()
    await db.refresh(new_invite)
    return new_invite

async def get_valid_invite(db: AsyncSession, invite_code: uuid.UUID) -> Optional[RegistrationInvite]:
    stmt = select(RegistrationInvite).where(
        RegistrationInvite.code == invite_code,
        RegistrationInvite.is_used == False
    )
    result = await db.execute(stmt)
    return result.scalars().first()

async def create_user_from_invite(db: AsyncSession, user_data: UserCreate, invite_code: uuid.UUID) -> Optional[User]:
    invite = await get_valid_invite(db, invite_code)
    if not invite:
        return None

    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        username=user_data.username,
        hashed_password=hashed_password,
        is_active=True,
        is_staff=True
    )
    db.add(new_user)
    
    invite.is_used = True
    db.add(invite)
    
    await db.commit()
    await db.refresh(new_user)
    
    return new_user

async def create_first_superuser(db: AsyncSession):
    """
    Создает первого суперпользователя из переменных окружения, если он не существует.
    """
    if settings.FIRST_SUPERUSER and settings.FIRST_SUPERUSER_PASSWORD:
        user = await get_user_by_username(db, settings.FIRST_SUPERUSER)
        if not user:
            try:
                hashed_password = get_password_hash(settings.FIRST_SUPERUSER_PASSWORD)
                new_user = User(
                    username=settings.FIRST_SUPERUSER,
                    hashed_password=hashed_password,
                    is_active=True,
                    is_staff=True,
                    is_superuser=True,
                    role=UserRole.ADMIN 
                )
                db.add(new_user)
                await db.commit()
                log.info(f"Первый суперпользователь '{settings.FIRST_SUPERUSER}' создан.")
            except IntegrityError:
                await db.rollback()
                log.info(f"Суперпользователь '{settings.FIRST_SUPERUSER}' уже был создан другим процессом.")
        else:
            log.info(f"Суперпользователь '{settings.FIRST_SUPERUSER}' уже существует.")