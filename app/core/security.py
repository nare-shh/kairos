from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

# ─── Password Hashing ─────────────────────────────────────────────────────────
# We use bcrypt directly (no passlib wrapper) — avoids version compatibility issues
# bcrypt is intentionally SLOW to compute — that's the point!
# Making it slow means brute-force attacks take years instead of seconds.

def hash_password(plain_password: str) -> str:
    """
    Takes "MyPassword1" → returns "$2b$12$eImiTXuWVxfM37uY4JANjQ..."

    How it works:
    1. bcrypt.gensalt() generates a random 22-character salt
    2. The password + salt are hashed using the Blowfish cipher
    3. The salt is embedded IN the hash string — no need to store it separately
    4. Same password hashed twice → different result (because salt is random)
    """
    password_bytes = plain_password.encode("utf-8")   # bcrypt works on bytes, not strings
    hashed_bytes = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed_bytes.decode("utf-8")               # store as string in the DB


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Checks if a plain password matches a stored hash.
    bcrypt extracts the salt from the hash, re-hashes the input, and compares.
    Returns True if match, False otherwise — NEVER raises an exception.
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        # checkpw can raise if hashed_password is malformed — treat as failed
        return False


# ─── JWT Tokens ───────────────────────────────────────────────────────────────
# JWT = JSON Web Token
# Structure: header.payload.signature (three parts separated by dots)
# Example: eyJhbGc...  .eyJ1c2VyX2lk...  .SflKxwRJSMeKKF2...
#          (algorithm)   (your data)       (cryptographic signature)
#
# The SIGNATURE is created using your SECRET_KEY.
# Anyone can READ the payload (it's base64 encoded, not encrypted)
# But nobody can FAKE the signature without the secret key.
# This is why you must NEVER expose your SECRET_KEY.

def create_access_token(user_id: str, role: str) -> str:
    """
    Access token: short-lived (30 min by default).
    Used on every API request in the Authorization header.
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {
        "sub": user_id,          # "sub" is a standard JWT claim for the subject (user id)
        "role": role,
        "exp": expire,           # "exp" is standard — JWT libraries check this automatically
        "type": "access",        # custom claim — prevents refresh tokens being used as access
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(user_id: str, role: str) -> str:
    """
    Refresh token: long-lived (7 days by default).
    Used ONLY to get a new access token when the old one expires.
    Should be stored securely (httpOnly cookie, not localStorage).
    """
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    payload = {
        "sub": user_id,
        "role": role,
        "exp": expire,
        "type": "refresh",       # different type — can't be used as access token
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    """
    Decodes and VERIFIES a JWT token.
    - Checks the signature (was this made with our secret key?)
    - Checks expiry (has this token expired?)
    - Returns the payload dict if valid
    - Raises JWTError if anything is wrong
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        raise   # let the caller handle this — don't swallow errors silently
