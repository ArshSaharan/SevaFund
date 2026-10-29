import datetime
import logging
import os
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models.user import User
from app.models.otp import OTPRecord
from app.config import settings
from app.schemas.user import (
    UserRegister,
    UserLogin,
    UserResponse,
    TokenResponse,
    GoogleAuthRequest,
    OTPSendRequest,
    OTPSendResponse,
    OTPVerifyRequest,
    MakeAdminRequest
)
from app.services.security import (
    hash_password,
    verify_password,
    create_access_token,
    normalize_indian_phone,
    generate_secure_otp,
    hash_otp,
    verify_otp_hash,
    verify_google_id_token
)
from app.services.auth_dependencies import (
    get_current_user,
    get_current_user_optional,
    require_admin
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

# ==============================================================================
# Email & Password Registration & Login
# ==============================================================================

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(user_in: UserRegister, db: Session = Depends(get_db)):
    """Registers a new user with email and secure password."""
    email_clean = user_in.email.strip().lower()
    existing = db.query(User).filter(User.email == email_clean).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists."
        )

    phone_clean = None
    if user_in.phone_number:
        try:
            phone_clean = normalize_indian_phone(user_in.phone_number)
            existing_phone = db.query(User).filter(User.phone_number == phone_clean).first()
            if existing_phone:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="An account with this phone number already exists."
                )
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    user = User(
        email=email_clean,
        phone_number=phone_clean,
        hashed_password=hash_password(user_in.password),
        full_name=user_in.full_name.strip(),
        avatar_url=user_in.avatar_url,
        role="USER",
        is_identity_verified=False
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": str(user.id), "role": user.role, "email": user.email})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )

@router.post("/login", response_model=TokenResponse)
def login(login_in: UserLogin, db: Session = Depends(get_db)):
    """Authenticates a user with email and password and returns a JWT token."""
    email_clean = login_in.email.strip().lower()
    user = db.query(User).filter(User.email == email_clean).first()
    if not user or not user.hashed_password or not verify_password(login_in.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    token = create_access_token({"sub": str(user.id), "role": user.role, "email": user.email})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )

# ==============================================================================
# Google OAuth 2.0 Authentication
# ==============================================================================

@router.post("/google", response_model=TokenResponse)
def google_auth(auth_in: GoogleAuthRequest, db: Session = Depends(get_db)):
    """
    Authenticates or registers a user via Google ID Token.
    Verifies the cryptographic signature against Google's public keys.
    """
    try:
        payload = verify_google_id_token(auth_in.id_token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid Google ID token: {str(e)}"
        )

    google_id = payload.get("sub")
    email = payload.get("email", "").lower().strip()
    name = payload.get("name", "Google Supporter")
    picture = payload.get("picture")

    # Find existing user by google_id or email
    user = None
    if google_id:
        user = db.query(User).filter(User.google_id == google_id).first()
    if not user and email:
        user = db.query(User).filter(User.email == email).first()

    if user:
        # Link google_id if not present
        if not user.google_id and google_id:
            user.google_id = google_id
        if picture and not user.avatar_url:
            user.avatar_url = picture
        user.is_email_verified = True
        user.is_identity_verified = True
        db.commit()
        db.refresh(user)
    else:
        # Create new verified user
        user = User(
            email=email or None,
            google_id=google_id,
            full_name=name,
            avatar_url=picture,
            role="USER",
            is_email_verified=True,
            is_identity_verified=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    token = create_access_token({"sub": str(user.id), "role": user.role, "email": user.email})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )

# ==============================================================================
# Indian Mobile OTP Authentication (6-digit crypto OTP)
# ==============================================================================

@router.post("/otp/send", response_model=OTPSendResponse)
async def send_otp(req: OTPSendRequest, db: Session = Depends(get_db)):
    """
    Sends a 6-digit OTP to an Indian mobile number (+91XXXXXXXXXX).
    Features rate limiting (max 3 attempts per 10 minutes) and secure hash storage.
    Sends real SMS if FAST2SMS_API_KEY or TWILIO credentials are set.
    """
    try:
        phone = normalize_indian_phone(req.phone_number)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # Rate limiting: max 3 OTP requests per 10 minutes per phone
    ten_minutes_ago = datetime.datetime.utcnow() - datetime.timedelta(minutes=10)
    recent_otps_count = (
        db.query(OTPRecord)
        .filter(OTPRecord.phone_number == phone, OTPRecord.created_at >= ten_minutes_ago)
        .count()
    )
    if recent_otps_count >= 3:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many OTP requests. Please wait 10 minutes before requesting again."
        )

    # Generate secure 6-digit OTP
    otp_code = generate_secure_otp()
    otp_hash = hash_otp(otp_code)
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=5)

    otp_record = OTPRecord(
        phone_number=phone,
        otp_code_hash=otp_hash,
        expires_at=expires_at
    )
    db.add(otp_record)
    db.commit()

    # Trigger real SMS dispatch (Fast2SMS / Twilio)
    from app.services.sms_service import send_real_sms_otp
    sms_status = await send_real_sms_otp(phone, otp_code)
    logger.info(f"📱 [SMS OTP] Status for {phone}: {sms_status}")

    sms_success = sms_status.get("success", False)
    sms_provider = sms_status.get("provider", "UNKNOWN")

    # In DEBUG mode, always return dev_otp so developers can test even if
    # the SMS gateway is unreachable, has no balance, or returns errors.
    is_debug = os.getenv("DEBUG", "False").lower() in ("true", "1")
    show_dev_otp = is_debug or sms_provider == "SIMULATION"

    if sms_success:
        msg = f"OTP sent to {phone} via {sms_provider}. Valid for 5 minutes."
    else:
        msg = f"OTP generated for {phone}. SMS delivery via {sms_provider} may have failed — check dev_otp below if in debug mode."
        logger.warning(f"⚠️ SMS delivery failed for {phone}: {sms_status}")

    return OTPSendResponse(
        phone_number=phone,
        message=msg,
        expires_in_seconds=300,
        dev_otp=otp_code if show_dev_otp else None
    )

@router.post("/otp/verify", response_model=TokenResponse)
def verify_otp(req: OTPVerifyRequest, db: Session = Depends(get_db)):
    """
    Verifies a 6-digit OTP for an Indian mobile number.
    Logs in or registers the user, locks after 5 failed attempts.
    """
    try:
        phone = normalize_indian_phone(req.phone_number)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    now = datetime.datetime.utcnow()
    # Find latest unverified OTP for this phone
    record = (
        db.query(OTPRecord)
        .filter(OTPRecord.phone_number == phone, OTPRecord.is_verified == False)
        .order_by(desc(OTPRecord.created_at))
        .first()
    )

    if not record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active OTP found. Please request a new OTP."
        )

    if record.expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP has expired. Please request a new OTP."
        )

    if record.attempts >= 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum verification attempts exceeded. Please request a new OTP."
        )

    # Verify code
    is_valid = verify_otp_hash(req.otp, record.otp_code_hash)
    if not is_valid:
        record.attempts += 1
        db.commit()
        remaining = 5 - record.attempts
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid OTP code. {remaining} attempt(s) remaining."
        )

    # Mark OTP as successfully verified
    record.is_verified = True
    db.commit()

    # Find or create user
    user = db.query(User).filter(User.phone_number == phone).first()
    if not user:
        user = User(
            phone_number=phone,
            full_name=req.full_name.strip() if req.full_name else f"Supporter {phone[-4:]}",
            role="USER",
            is_phone_verified=True,
            is_identity_verified=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        user.is_phone_verified = True
        user.is_identity_verified = True
        if req.full_name and (not user.full_name or user.full_name.startswith("Supporter")):
            user.full_name = req.full_name.strip()
        db.commit()
        db.refresh(user)

    token = create_access_token({"sub": str(user.id), "role": user.role, "phone": user.phone_number})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )

# ==============================================================================
# Profile & Admin Promotion
# ==============================================================================

@router.get("/me", response_model=UserResponse)
def get_profile(current_user: User = Depends(get_current_user)):
    """Returns the authenticated user's profile."""
    return UserResponse.model_validate(current_user)

@router.post("/promote-admin", response_model=UserResponse)
def promote_user_to_admin(
    req: MakeAdminRequest,
    db: Session = Depends(get_db)
):
    """
    Secure endpoint to promote a user to ADMIN role using platform master SECRET_KEY.
    """
    if req.secret_key != settings.SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid secret key. Admin promotion unauthorized."
        )

    user = db.query(User).filter(User.id == req.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    user.role = "ADMIN"
    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)
