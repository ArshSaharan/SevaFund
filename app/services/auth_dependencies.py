from typing import Optional
from fastapi import Depends, HTTPException, Header, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.services.security import decode_access_token

def get_current_user_optional(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Extracts and validates user from Authorization: Bearer <token>.
    Supports standard JWT tokens and legacy 'user_<id>' for backward compatibility.
    """
    if not authorization:
        return None
        
    token = authorization.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
        
    if not token:
        return None

    # 1. Try decoding standard JWT
    payload = decode_access_token(token)
    if payload and "sub" in payload:
        try:
            user_id = int(payload["sub"])
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                return user
        except (ValueError, TypeError):
            pass

    # 2. Legacy fallback token scheme (user_<id>)
    if token.startswith("user_"):
        try:
            user_id = int(token.replace("user_", ""))
            return db.query(User).filter(User.id == user_id).first()
        except ValueError:
            return None

    return None

def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> User:
    """
    Strictly requires an authenticated user.
    If no authorization header or invalid token is supplied, raises HTTP 401.
    """
    user = get_current_user_optional(authorization, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials are required or have expired.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return user

def get_current_user_or_demo(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> User:
    """
    Used for endpoints where demo convenience is helpful if no token is passed.
    """
    user = get_current_user_optional(authorization, db)
    if user:
        return user
        
    demo_user = db.query(User).filter(User.email == "organizer@crowdfund-demo.com").first()
    if not demo_user:
        demo_user = User(
            email="organizer@crowdfund-demo.com",
            full_name="Sarah Jenkins",
            role="USER",
            is_identity_verified=True
        )
        db.add(demo_user)
        db.commit()
        db.refresh(demo_user)
    return demo_user

def require_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Strict Role-Based Access Control: ONLY administrators can access.
    Non-admin users receive a strict 403 Forbidden.
    """
    if current_user.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Admin privileges required. Only platform administrators can accept or reject fundraisers."
        )
    return current_user

def require_trust_reviewer_or_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Requires either TRUST_REVIEWER or ADMIN role.
    """
    if current_user.role not in ["ADMIN", "TRUST_REVIEWER"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Moderator or Administrator access required."
        )
    return current_user
