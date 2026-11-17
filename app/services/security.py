import os
import re
import secrets
import hashlib
import datetime
from typing import Optional, Dict, Any
import jwt
import bcrypt

from app.config import settings

# ==============================================================================
# Signing key: fail closed unless a strong, private SECRET_KEY is configured
# ==============================================================================

MIN_SIGNING_KEY_CHARS = 32
# SHA-256 fingerprints of signing keys that are publicly known (the app/config.py fallback default and the value
# that was published in .env.example).  Only fingerprints are stored, never the keys.
_PUBLIC_SIGNING_KEY_SHA256 = {
    "aa46cf8b9b464f63227d9b174c36f301a6ee78c58400330847fdc77ceaf53c3c",
    "1c9a3557b02c551028384b6e56582a853b00eef9aa97f6af58d4bc4c9342199e",
}
_PLACEHOLDER_KEY = re.compile(r"^(replace[_-]?me|change[_-]?me|your[_-]|example|placeholder|secret$|changeit)", re.I)


class InsecureSigningKeyError(RuntimeError):
    """Raised at import time so the application refuses to start with a missing or publicly known key."""


def require_signing_key(key: Optional[str]) -> str:
    """Return the key if it is safe to sign tokens with; otherwise raise.  The key is never included in errors."""
    key = key or ""
    problem = None
    if not key.strip():
        problem = "SECRET_KEY is not set"
    elif hashlib.sha256(key.encode("utf-8")).hexdigest() in _PUBLIC_SIGNING_KEY_SHA256:
        problem = "SECRET_KEY is a publicly known value"
    elif _PLACEHOLDER_KEY.search(key.strip()):
        problem = "SECRET_KEY is a placeholder"
    elif len(key) < MIN_SIGNING_KEY_CHARS or len(set(key)) < 10:
        problem = f"SECRET_KEY is too weak (use at least {MIN_SIGNING_KEY_CHARS} random characters)"
    if problem:
        raise InsecureSigningKeyError(
            f"{problem}. Refusing to start. Put a random value in .env, for example the output of: "
            'python3 -c "import secrets; print(secrets.token_urlsafe(64))"')
    return key


# JWT Config
JWT_SECRET = require_signing_key(settings.SECRET_KEY)
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

# ==============================================================================
# Password Hashing & Verification (Bcrypt + Legacy SHA256 fallback)
# ==============================================================================

def hash_password(password: str) -> str:
    """Hashes a password securely using bcrypt."""
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")

def verify_password(plain_password: str, stored_hash: Optional[str]) -> bool:
    """
    Verifies a plain password against stored hash.
    Supports standard bcrypt and legacy sha256$ format for backward compatibility.
    """
    if not stored_hash or not plain_password:
        return False
        
    # Check if legacy sha256 format (salt$hash)
    if "$" in stored_hash and not stored_hash.startswith("$2"):
        parts = stored_hash.split("$", 1)
        if len(parts) == 2:
            salt, hashed = parts
            computed = hashlib.sha256(f"{salt}{plain_password}".encode("utf-8")).hexdigest()
            return secrets.compare_digest(computed, hashed)
            
    # Standard bcrypt check
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), stored_hash.encode("utf-8"))
    except Exception:
        return False

# ==============================================================================
# JWT Tokens (RFC 7519 Compliant)
# ==============================================================================

def create_access_token(data: Dict[str, Any], expires_delta: Optional[datetime.timedelta] = None) -> str:
    """Creates a signed JWT access token with payload, exp and iat."""
    to_encode = data.copy()
    now = datetime.datetime.utcnow()
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + datetime.timedelta(minutes=JWT_EXPIRATION_MINUTES)
        
    to_encode.update({
        "exp": expire,
        "iat": now,
        "iss": "sevafund-india-api"
    })
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decodes and validates a JWT access token."""
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "iat"]}
        )
        return payload
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None

# ==============================================================================
# Indian Phone Number Validation & Formatting
# ==============================================================================

INDIAN_PHONE_REGEX = re.compile(r"^(?:\+91|91|0)?[6-9]\d{9}$")

def normalize_indian_phone(phone: str) -> str:
    """
    Validates and formats an Indian mobile number into standard +91XXXXXXXXXX.
    Indian mobiles start with 6, 7, 8, or 9 and are 10 digits long.
    """
    cleaned = re.sub(r"[\s\-\(\)]", "", phone.strip())
    if not INDIAN_PHONE_REGEX.match(cleaned):
        raise ValueError("Invalid Indian mobile number. Must be a valid 10-digit number starting with 6-9.")
    
    # Strip leading +91, 91, or 0
    if cleaned.startswith("+91"):
        cleaned = cleaned[3:]
    elif cleaned.startswith("91") and len(cleaned) == 12:
        cleaned = cleaned[2:]
    elif cleaned.startswith("0") and len(cleaned) == 11:
        cleaned = cleaned[1:]
        
    return f"+91{cleaned}"

# ==============================================================================
# Mobile OTP Generator & Verifier
# ==============================================================================

def generate_secure_otp() -> str:
    """Generates a cryptographically strong 6-digit numeric OTP."""
    code = secrets.randbelow(900000) + 100000
    return str(code)

def hash_otp(otp: str, salt: Optional[str] = None) -> str:
    """Hashes an OTP before storing in database for protection at rest."""
    if not salt:
        salt = secrets.token_hex(8)
    hashed = hashlib.sha256(f"{salt}:{otp}".encode("utf-8")).hexdigest()
    return f"{salt}${hashed}"

def verify_otp_hash(plain_otp: str, stored_hash: str) -> bool:
    """Verifies user-entered OTP against the stored hash."""
    if not stored_hash or "$" not in stored_hash:
        return False
    salt, hashed = stored_hash.split("$", 1)
    computed = hashlib.sha256(f"{salt}:{plain_otp.strip()}".encode("utf-8")).hexdigest()
    return secrets.compare_digest(computed, hashed)

# ==============================================================================
# Google OAuth Token Verification
# ==============================================================================

GOOGLE_ISSUERS = ("accounts.google.com", "https://accounts.google.com")


class GoogleSignInUnavailable(Exception):
    """Google sign-in is not securely configured on this server; sign-in fails closed."""


class InvalidGoogleToken(Exception):
    """The token is not a valid, verified Google ID token for this application."""


def google_client_id() -> Optional[str]:
    """The OAuth client ID that ID tokens must be issued for (their audience), or None if not configured."""
    value = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    if not value.endswith(".apps.googleusercontent.com") or _PLACEHOLDER_KEY.search(value):
        return None
    return value


def _google_request():
    """Transport used to fetch Google's signing certificates.  Tests replace this with an isolated fixture."""
    from google.auth.transport import requests as google_requests
    return google_requests.Request()


def verify_google_id_token(id_token_str: str) -> Dict[str, Any]:
    """
    Verifies a Google ID token with Google's library: RS256 signature against Google's published certificates,
    expiry, audience (this server's GOOGLE_CLIENT_ID) and issuer, and requires a verified email address.
    There is no test or development bypass.  Without a configured client ID it fails closed.
    """
    client_id = google_client_id()
    if not client_id:
        raise GoogleSignInUnavailable("Google sign-in is not configured on this server.")
    try:
        from google.auth import exceptions as google_exceptions
        from google.oauth2 import id_token as google_id_token
        request = _google_request()
    except ImportError as exc:
        raise GoogleSignInUnavailable("Google sign-in support is not installed on this server.") from exc
    try:
        id_info = google_id_token.verify_oauth2_token(id_token_str, request, audience=client_id)
    except google_exceptions.TransportError as exc:
        raise GoogleSignInUnavailable("Google's signing certificates could not be fetched.") from exc
    except Exception as exc:          # bad signature, expired, wrong audience or issuer, malformed token
        raise InvalidGoogleToken("Google ID token could not be verified.") from exc
    if id_info.get("iss") not in GOOGLE_ISSUERS or id_info.get("aud") != client_id:
        raise InvalidGoogleToken("Google ID token was not issued by Google for this application.")
    if not id_info.get("sub") or not id_info.get("email") or id_info.get("email_verified") is not True:
        raise InvalidGoogleToken("Google account has no verified email address.")
    return {
        "email": id_info["email"],
        "name": id_info.get("name", "Google User"),
        "sub": id_info["sub"],
        "picture": id_info.get("picture"),
        "email_verified": True,
    }
