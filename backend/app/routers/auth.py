import os
import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import UserCreate, UserLogin, UserOut, Token
from app.auth.security import (
    verify_password,
    get_password_hash,
    create_access_token,
)
from app.auth.deps import get_current_user
from app.config import settings


router = APIRouter(prefix="/auth", tags=["Authentication"])


# ============================================================
# REGISTER
# ============================================================

@router.post(
    "/register",
    response_model=Token,
    status_code=status.HTTP_201_CREATED
)
def register(
    user_in: UserCreate,
    db: Session = Depends(get_db)
):
    existing_user = (
        db.query(User)
        .filter(User.email == user_in.email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="A user with this email already exists."
        )

    user = User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        full_name=(
            user_in.full_name
            or user_in.email.split("@")[0].capitalize()
        )
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    access_token_expires = timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )

    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "email": user.email
        },
        expires_delta=access_token_expires
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user
    }


# ============================================================
# LOGIN
# ============================================================

@router.post("/login", response_model=Token)
def login(
    user_in: UserLogin,
    db: Session = Depends(get_db)
):
    user = (
        db.query(User)
        .filter(User.email == user_in.email)
        .first()
    )

    if not user or not verify_password(
        user_in.password,
        user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )

    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "email": user.email
        },
        expires_delta=access_token_expires
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user
    }


# ============================================================
# CURRENT USER
# ============================================================

@router.get("/me", response_model=UserOut)
def get_current_user_profile(
    current_user: User = Depends(get_current_user)
):
    return current_user

@router.get("/admin-list-users")
def admin_list_users(
    admin_secret: str = Header(
        ...,
        alias="X-Admin-Reset-Secret"
    ),
    db: Session = Depends(get_db)
):
    expected_secret = os.getenv(
        "ADMIN_RESET_SECRET",
        ""
    )

    if not expected_secret:
        raise HTTPException(
            status_code=500,
            detail="Admin reset secret is not configured."
        )

    if not secrets.compare_digest(
        admin_secret,
        expected_secret
    ):
        raise HTTPException(
            status_code=403,
            detail="Invalid admin reset secret."
        )

    users = db.query(User).all()

    return [
        {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name
        }
        for user in users
    ]
# ============================================================
# TEMPORARY ADMIN PASSWORD RESET
# REMOVE THIS ENDPOINT AFTER RESETTING THE PASSWORD
# ============================================================

@router.post("/admin-reset-password")
def admin_reset_password(
    email: str,
    new_password: str,
    admin_secret: str = Header(
        ...,
        alias="X-Admin-Reset-Secret"
    ),
    db: Session = Depends(get_db)
):
    # Get the secret stored in Render Environment Variables
    expected_secret = os.getenv(
        "ADMIN_RESET_SECRET",
        ""
    )

    # Check whether the secret is configured
    if not expected_secret:
        raise HTTPException(
            status_code=500,
            detail="Admin reset secret is not configured."
        )

    # Secure comparison
    if not secrets.compare_digest(
        admin_secret,
        expected_secret
    ):
        raise HTTPException(
            status_code=403,
            detail="Invalid admin reset secret."
        )

    # Find the user
    user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found."
        )

    # Hash the new password
    user.hashed_password = get_password_hash(
        new_password
    )

    db.commit()

    return {
        "message": "Password reset successfully."
    }