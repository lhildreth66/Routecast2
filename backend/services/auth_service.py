"""
Authentication Service for RouteCast
Handles JWT tokens, password hashing, and user authentication
"""
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from passlib.context import CryptContext
from jose import JWTError, jwt
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Configuration
JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'your-secret-key-change-in-production')
JWT_ALGORITHM = os.environ.get('JWT_ALGORITHM', 'HS256')
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get('ACCESS_TOKEN_EXPIRE_MINUTES', 30))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.environ.get('REFRESH_TOKEN_EXPIRE_DAYS', 7))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({
        "exp": expire,
        "type": "access"
    })
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT refresh token"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))
    to_encode.update({
        "exp": expire,
        "type": "refresh"
    })
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_tokens(user_id: str, email: str) -> Tuple[str, str, int]:
    """Create both access and refresh tokens"""
    token_data = {"sub": user_id, "email": email}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    return access_token, refresh_token, ACCESS_TOKEN_EXPIRE_MINUTES * 60


def verify_token(token: str, token_type: str = "access") -> Optional[dict]:
    """Verify a JWT token and return its payload"""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != token_type:
            return None
        return payload
    except JWTError:
        return None


def generate_verification_token() -> str:
    """Generate a secure token for email verification or password reset"""
    return secrets.token_urlsafe(32)


async def get_user_by_email(db: AsyncIOMotorDatabase, email: str) -> Optional[dict]:
    """Get a user by email from database"""
    return await db.users.find_one({"email": email.lower()})


async def get_user_by_id(db: AsyncIOMotorDatabase, user_id: str) -> Optional[dict]:
    """Get a user by ID from database"""
    return await db.users.find_one({"user_id": user_id})


async def create_user(db: AsyncIOMotorDatabase, email: str, password: str, name: Optional[str] = None, pending_plan: str = "monthly") -> dict:
    """Create a new user in the database"""
    import uuid

    now = datetime.now(timezone.utc)
    user_data = {
        "user_id": str(uuid.uuid4()),
        "email": email.lower(),
        "name": name,
        "hashed_password": get_password_hash(password),
        "email_verified": False,
        "pending_plan": pending_plan if pending_plan in ("monthly", "yearly") else "monthly",
        "created_at": now,
        "updated_at": now,
        "subscription_status": "inactive",
        "subscription_provider": None,
        "subscription_plan": "free",
        "subscription_expiration": None,
        "stripe_customer_id": None,
        "stripe_subscription_id": None,
        "apple_original_transaction_id": None,
        "google_purchase_token": None,
        "trial_used": False,
        "trial_start": None,
        "trial_end": None,
    }

    await db.users.insert_one(user_data)
    return user_data


async def update_user(db: AsyncIOMotorDatabase, user_id: str, update_data: dict) -> bool:
    """Update user data in database"""
    update_data["updated_at"] = datetime.now(timezone.utc)
    result = await db.users.update_one(
        {"user_id": user_id},
        {"$set": update_data}
    )
    return result.modified_count > 0


async def store_verification_token(db: AsyncIOMotorDatabase, user_id: str, token: str, token_type: str, expires_hours: int = 24) -> bool:
    """Store a verification token in the database"""
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=expires_hours)
    safe_preview = f"{token[:6]}...{token[-6:]}" if len(token) >= 12 else "<short>"

    doc = {
        "user_id": user_id,
        "token": token,
        "token_type": token_type,
        "created_at": now,
        "expires_at": expires_at,
        "used": False
    }
    result = await db.verification_tokens.insert_one(doc)
    logger.info(
        f"[TOKEN] stored type={token_type!r} preview={safe_preview} "
        f"user_id={user_id} expires_at={expires_at.isoformat()} "
        f"db_id={result.inserted_id}"
    )
    return True


async def verify_and_consume_token(db: AsyncIOMotorDatabase, token: str, token_type: str) -> Optional[str]:
    """Verify a token and mark it as used. Returns user_id if valid."""
    safe_preview = f"{token[:6]}...{token[-6:]}" if len(token) >= 12 else "<short>"
    logger.info(f"[TOKEN] verify attempt type={token_type!r} len={len(token)} preview={safe_preview}")

    now = datetime.now(timezone.utc)
    token_doc = await db.verification_tokens.find_one({
        "token": token,
        "token_type": token_type,
        "used": False,
        "expires_at": {"$gt": now}
    })

    if not token_doc:
        # Detailed diagnostic: distinguish not-found vs expired vs already-used
        any_doc = await db.verification_tokens.find_one(
            {"token": token, "token_type": token_type}
        )
        if any_doc is None:
            logger.warning(
                f"[TOKEN] FAIL type={token_type!r} preview={safe_preview} "
                "reason=not_found (token does not exist in DB)"
            )
        elif any_doc.get("used"):
            uid = any_doc.get("user_id", "unknown")
            logger.warning(
                f"[TOKEN] FAIL type={token_type!r} preview={safe_preview} "
                f"reason=already_used user_id={uid}"
            )
        else:
            expires_at = any_doc.get("expires_at")
            uid = any_doc.get("user_id", "unknown")
            logger.warning(
                f"[TOKEN] FAIL type={token_type!r} preview={safe_preview} "
                f"reason=expired expired_at={expires_at} user_id={uid}"
            )
        return None

    user_id = token_doc["user_id"]
    logger.info(f"[TOKEN] valid type={token_type!r} preview={safe_preview} user_id={user_id} — marking used")

    # Mark token as used
    await db.verification_tokens.update_one(
        {"_id": token_doc["_id"]},
        {"$set": {"used": True}}
    )

    return user_id


async def authenticate_user(db: AsyncIOMotorDatabase, email: str, password: str) -> Optional[dict]:
    """Authenticate a user with email and password"""
    user = await get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user["hashed_password"]):
        return None
    return user
