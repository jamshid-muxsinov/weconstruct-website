from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.core.db import get_db_session
from src.models.shop_models import User
from src.services.user_service import get_user_by_username
from src.schemas.user_schemas import TokenData

settings = get_settings()

# Мы создаем зависимость, которая будет искать токен
class OAuth2PasswordBearerWithCookie(OAuth2PasswordBearer):
    async def __call__(self, request: Request) -> Optional[str]:
        # Сначала ищем в заголовке Authorization (стандартный способ)
        authorization: str = request.headers.get("Authorization")
        scheme, _, param = authorization.partition(" ")
        if authorization and scheme.lower() == "bearer":
            return param
        
        # Если в заголовке нет, ищем в cookie
        token = request.cookies.get("access_token")
        if token:
            return token
        
        # Если нигде нет, будет ошибка (но мы позволим ей быть опциональной)
        # В нашем случае get_current_user обработает None
        return None

# Инициализируем нашу кастомную схему
oauth2_scheme = OAuth2PasswordBearerWithCookie(tokenUrl="/admin/login/token", auto_error=False)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

async def get_current_user(
    db: AsyncSession = Depends(get_db_session), 
    token: Optional[str] = Depends(oauth2_scheme) # <-- Используем нашу новую зависимость
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_303_SEE_OTHER, # <-- Меняем на 303 для редиректа
        detail="Could not validate credentials, please log in again",
        headers={"Location": "/admin/login"}, # <-- Указываем куда редиректить
    )
    if token is None:
        raise credentials_exception
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        
        exp = payload.get("exp")
        if exp is None or datetime.now(timezone.utc).timestamp() > exp:
            raise credentials_exception
            
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
        
    user = await get_user_by_username(db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

async def get_current_staff_user(current_user: User = Depends(get_current_active_user)) -> User:
    if not current_user.is_staff:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Insufficient permissions. Staff access required."
        )
    return current_user

async def get_current_superuser(current_user: User = Depends(get_current_active_user)) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Доступ запрещен. Требуются права администратора."
        )
    return current_user