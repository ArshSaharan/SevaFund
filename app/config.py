import os
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseModel):
    APP_NAME: str = "India Crowdfund & AI Trust Platform"
    APP_VERSION: str = "1.0.0"
    API_PREFIX: str = "/api"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() in ("true", "1")
    
    # Currency
    DEFAULT_CURRENCY: str = "INR"
    DEFAULT_CURRENCY_SYMBOL: str = "₹"
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./crowdfund.db")
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "super-secret-crowdfund-jwt-key-change-in-production")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    # AI Engine Configuration
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    
    # AI Trust & Safety Thresholds
    AI_AUTO_APPROVE_SCORE_THRESHOLD: float = 80.0
    AI_REVIEW_SCORE_THRESHOLD: float = 50.0  # Between 50 and 80 needs human admin review
    
    # Indian Financials (Ketto / Milaap standard: 0% platform fee, Razorpay/Cashfree standard 2% + 18% GST = ~2.36%)
    PLATFORM_FEE_PERCENTAGE: float = 0.00
    GATEWAY_FEE_PERCENTAGE: float = 0.02  # 2% standard Indian gateway fee
    GATEWAY_GST_PERCENTAGE: float = 0.18  # 18% GST on gateway fee
    UPI_FIXED_FEE_INR: float = 0.00       # 0 fee for standard UPI P2M / lower tiers

    # Razorpay Payment Gateway
    RAZORPAY_KEY_ID: str = os.getenv("RAZORPAY_KEY_ID", "rzp_test_sevafund_demo")
    RAZORPAY_KEY_SECRET: str = os.getenv("RAZORPAY_KEY_SECRET", "mock_razorpay_secret")

settings = Settings()
