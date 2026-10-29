from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import engine, Base
from app.routers import (
    auth_router,
    campaigns_router,
    donations_router,
    updates_router,
    payouts_router,
    ai_router,
    admin_router
)

# Initialize database schema tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
# India Crowdfunding API with AI Trust & Authenticity Verification

Production-ready backend platform mirroring leading Indian crowdfunding architectures (Milaap / Ketto / ImpactGuru style).

### Key Modules:
- **Campaigns in INR (₹)**: Goal tracking in Lakhs/Crores, hospital UHID verification, direct hospital bank settlement, 80G tax exempt badges.
- **AI Indian Trust & Verification**: Automated multi-factor authenticity scoring (cost plausibility benchmarking against Indian hospital averages like AIIMS, Tata Memorial, Apollo, Fortis; entity specificity; fake ayurvedic / personal UPI red-flag detection).
- **Indian Payments (UPI / Netbanking / RuPay)**: Real-time donation processing via UPI (GPay, PhonePe, Paytm, BHIM) and Netbanking, 0% platform fee, 80G tax deduction receipts with donor PAN card compliance.
- **Updates & Milestones**: Clinical recovery updates and pharmacy/hospital receipt proofs.
- **Indian Payouts**: Secure withdrawals via NEFT / IMPS / RTGS with 11-digit IFSC code verification or Direct Hospital Account settlement.
- **AI Story Assistant**: Converts rough Hindi/English notes into transparent, high-trust fundraising pitches with itemized INR budget breakdowns.
- **Admin Trust & Safety**: Moderator triage queue for flagged or borderline campaigns.
    """,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS for universal frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Industry Security Headers Middleware
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

# Register API Routers
app.include_router(auth_router, prefix=settings.API_PREFIX)
app.include_router(campaigns_router, prefix=settings.API_PREFIX)
app.include_router(donations_router, prefix=settings.API_PREFIX)
app.include_router(updates_router, prefix=settings.API_PREFIX)
app.include_router(payouts_router, prefix=settings.API_PREFIX)
app.include_router(ai_router, prefix=settings.API_PREFIX)
app.include_router(admin_router, prefix=settings.API_PREFIX)

@app.get("/", tags=["Health"])
def root_index():
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "documentation": "/docs",
        "endpoints": {
            "campaigns": f"{settings.API_PREFIX}/campaigns",
            "ai_verification": f"{settings.API_PREFIX}/ai/verify-request",
            "ai_story_enhancer": f"{settings.API_PREFIX}/ai/enhance-story",
            "cost_benchmarking": f"{settings.API_PREFIX}/ai/benchmark-cost",
            "admin_flagged": f"{settings.API_PREFIX}/admin/flagged"
        }
    }

@app.get("/api/health", tags=["Health"])
def health_check():
    return {
        "status": "up",
        "version": settings.APP_VERSION,
        "ai_engine": "active"
    }
