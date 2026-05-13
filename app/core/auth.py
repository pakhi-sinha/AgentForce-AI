from datetime import datetime, timedelta
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.db.users import get_user_by_id

security = HTTPBearer()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode())
    except Exception:
        return False


def create_access_token(user_id: str, expires_delta: Optional[timedelta] = None) -> str:
    expire = datetime.utcnow() + (expires_delta or timedelta(seconds=settings.jwt_exp_seconds))
    payload = {"sub": user_id, "exp": expire}
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> dict:
    token = credentials.credentials
    payload = decode_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user
