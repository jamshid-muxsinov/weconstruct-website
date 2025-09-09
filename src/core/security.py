# src/core/security.py

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

class OAuth2PasswordBearerWithCookie(OAuth2PasswordBearer):
    async def __call__(self, request: Request) -> Optional[str]:
        authorization: str = request.headers.get("Authorization")
        
        # Проверяем, что заголовок существует, перед тем как его парсить
        if authorization:
            scheme, _, param = authorization.partition(" ")
            if scheme.lower() == "bearer":
                return param
        
        # Если в заголовке нет, ищем в cookie
        token = request.cookies.get("access_token")
        if token:
            return token
        
        return None

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

# --- ЕДИНСТВЕННАЯ И ПРАВИЛЬНАЯ ВЕРСИЯ ЭТОЙ ФУНКЦИИ ---
async def get_current_user(
    request: Request, # <-- `request` теперь является зависимостью
    db: AsyncSession = Depends(get_db_session), 
    token: Optional[str] = Depends(oauth2_scheme)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_303_SEE_OTHER,
        detail="Not authenticated",
        # Теперь `request.url_for` будет работать, так как `request` доступен
        headers={"Location": str(request.url_for("admin_login"))},
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