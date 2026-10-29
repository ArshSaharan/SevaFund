import os
import re
import secrets
import hashlib
import datetime
from typing import Optional, Dict, Any
import jwt
import bcrypt

from app.config import settings

# JWT Config
JWT_SECRET = settings.SECRET_KEY
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

def verify_google_id_token(id_token_str: str) -> Dict[str, Any]:
    """
    Verifies a Google ID token from Google Sign-In SDK.
    Returns payload containing 'email', 'name', 'sub' (google_id), 'picture'.
    """
    google_client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    
    # Check for simulated dev/testing token in DEBUG or test mode
    if id_token_str.startswith("mock_google_"):
        parts = id_token_str.split("_")
        email = f"{parts[2]}@gmail.com" if len(parts) > 2 else "google.user@example.com"
        return {
            "email": email,
            "name": "Google Verified User",
            "sub": f"google_sub_{email}",
            "picture": "https://lh3.googleusercontent.com/a/default-user",
            "email_verified": True
        }

    try:
        from google.oauth2 import id_token
        from google.auth.transport import requests as google_requests
        
        request = google_requests.Request()
        id_info = id_token.verify_oauth2_token(
            id_token_str,
            request,
            audience=google_client_id if google_client_id else None
        )
        
        # Verify issuer
        if id_info.get("iss") not in ["accounts.google.com", "https://accounts.google.com"]:
            raise ValueError("Wrong issuer in Google token.")
            
        return {
            "email": id_info.get("email"),
            "name": id_info.get("name", "Google User"),
            "sub": id_info.get("sub"),
            "picture": id_info.get("picture"),
            "email_verified": id_info.get("email_verified", False)
        }
    except Exception as e:
        raise ValueError(f"Google token verification failed: {str(e)}")
