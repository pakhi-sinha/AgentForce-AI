from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from app.api.schemas import SignupRequest, LoginRequest, ForgotPasswordRequest, UserResponse
from app.core.auth import hash_password, verify_password, create_access_token, get_current_user
from app.db.users import create_user, get_user_by_email, get_user_by_username, update_password_by_email

router = APIRouter()


@router.post("/signup")
async def signup(payload: SignupRequest):
    existing = get_user_by_email(payload.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    if get_user_by_username(payload.username):
        raise HTTPException(status_code=400, detail="Username already registered")
    password_hash = hash_password(payload.password)
    user = create_user(payload.username, payload.email, password_hash)
    token = create_access_token(user["id"])
    return JSONResponse({"access_token": token, "token_type": "bearer", "user": user})


@router.post("/login")
async def login(payload: LoginRequest):
    user = get_user_by_email(payload.email)
    if not user or not verify_password(payload.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(user["id"])
    public = {k: user[k] for k in ("id", "username", "email", "created_at")}
    return JSONResponse({"access_token": token, "token_type": "bearer", "user": public})


@router.post("/forgot-password")
async def forgot_password(payload: ForgotPasswordRequest):
    user = get_user_by_email(payload.email)
    if not user:
        raise HTTPException(status_code=404, detail="No account found for this email.")
    updated = update_password_by_email(payload.email, hash_password(payload.new_password))
    if not updated:
        raise HTTPException(status_code=500, detail="Could not update password. Please try again.")
    return JSONResponse({"status": "ok", "message": "Password updated successfully. Please login."})


@router.get("/me", response_model=UserResponse)
async def me(current_user: dict = Depends(get_current_user)):
    return current_user
