# SevaFund India - AI-Verified Crowdfunding Platform

SevaFund India is a full-stack crowdfunding platform built specifically for the Indian healthcare and social cause ecosystem. It combines a FastAPI backend with an Angular 18 frontend, featuring an automated AI trust and authenticity verification pipeline, Razorpay payment processing with automated Section 80G tax receipts, Indian mobile SMS OTP authentication via Fast2SMS, Google OAuth 2.0 single sign-on, and an administrative ledger.

---

## Architecture Overview

SevaFund addresses critical challenges unique to Indian crowdfunding:

1. **Healthcare Cost Realities**: Medical treatments in premier Indian hospital networks (AIIMS, Tata Memorial, Apollo, Fortis, Max Healthcare, CMC Vellore) follow distinct cost bands (for example, Leukemia chemotherapy ranges from 3 to 25 Lakh INR). The platform validates funding goals against an Indian hospital cost matrix.
2. **Fraud Prevention**: An automated verification pipeline analyzes campaign descriptions, hospital estimates, UHID (Unique Hospital Identification) numbers, doctor credentials, and flags suspicious solicitations (such as redirecting to personal UPI accounts or unverified alternative treatments).
3. **Indian Payment Flows**: Full support for Razorpay payment checkout covering UPI (Google Pay, PhonePe, Paytm, BHIM), Netbanking across major Indian banks, and Debit/Credit cards. The platform operates on a 0% platform fee model with optional voluntary tips.
4. **Tax Compliance**: Automated generation of Section 80G tax exemption certificates under the Indian Income Tax Act, including mandatory PAN collection for high-value donations.
5. **Beneficiary Transparency**: Direct-to-hospital and beneficiary tracking so donors and administrators can inspect the exact fund recipient for every campaign.

---

## Key Features

### 1. AI Authenticity and Verification Pipeline
- **Cost Plausibility Engine (30% weight)**: Cross-checks campaign targets against standard Indian medical benchmarks across oncology, cardiology, organ transplants, critical care, and disaster relief.
- **Factual Specificity Analysis (25% weight)**: Detects verified hospital networks, attending physicians, diagnosis terms, patient UHID numbers, and geographic relevance.
- **Red Flag and Risk Scanner (25% weight)**: Flags requests attempting to divert funds to personal phone numbers, off-platform UPI handles, or unverified claims.
- **Document Verification (20% weight)**: Audits supporting hospital estimate letters, discharge summaries, Ayushman Bharat (PM-JAY) cards, and government identity proofs.
- **Automated Workflow**:
  - Score >= 80.0: Automatically approved and published as ACTIVE.
  - 50.0 <= Score < 80.0: FLAGGED for human moderator review.
  - Score < 50.0: REJECTED with detailed feedback for the organizer.

### 2. Payment Gateway and 80G Tax Deductions
- **Razorpay Integration**: Supports live and test gateway orders via Razorpay Checkout modal, with fallback simulation mode for local development.
- **Payment Methods**: Direct UPI QR and intents, Netbanking (SBI, HDFC, ICICI, Axis, PNB), and Card processing.
- **Section 80G Certificates**: Instant generation of digital tax receipts with unique registration numbers (`80G-YYYY-XXXXX`), donor PAN, and downloadable format.
- **Direct Recipient Transparency**: Every campaign clearly displays the verified beneficiary or hospital billing desk receiving the disbursements.

### 3. Authentication and Security
- **Indian Mobile OTP**: One-time password verification sent to Indian (+91) phone numbers via the Fast2SMS gateway with automatic fallback to quick SMS routes.
- **Google OAuth 2.0**: Direct sign-in using Google Identity Services (GIS) with secure backend ID token validation.
- **Role-Based Access Control**: Protected routes using JWT (JSON Web Tokens) with passlib password hashing for organizers, donors, and administrators.

### 4. Administrative Ledger and Governance
- **Donation Ledger**: Administrators can inspect complete transaction histories, including donor identities, contact numbers, PAN records, payment gateway order IDs, transaction references, and beneficiary names.
- **Campaign Review**: Real-time review queue to approve, reject, or flag campaigns with AI-generated risk rationale and document inspection.

---

## Tech Stack

- **Backend**: Python 3.9+, FastAPI, SQLAlchemy, Pydantic v2, Uvicorn
- **Frontend**: Angular 18 (Standalone Components, Signals), TypeScript, Tailwind CSS
- **Database**: SQLite (default for development), fully compatible with PostgreSQL
- **AI Engine**: Google Gemini 2.5 Flash API (with rule-based heuristic fallback)
- **SMS Gateway**: Fast2SMS API (Indian telecom routing)
- **Payment Processing**: Razorpay Python SDK and Razorpay Checkout.js
- **Authentication**: Google OAuth 2.0 (GIS) and JWT with bcrypt password hashing

---

## Project Structure

```
crowdfunding/
|-- app/
|   |-- config.py              # Environment settings and configuration
|   |-- database.py            # SQLAlchemy database engine and session
|   |-- main.py                # FastAPI application entrypoint and middleware
|   |-- models/                # SQLAlchemy database models
|   |   |-- user.py            # User and authentication model
|   |   |-- campaign.py        # Campaign, updates, and documents model
|   |   |-- donation.py        # Donations, 80G receipts, and gateway fields
|   |   `-- verification.py    # AI verification audit log model
|   |-- routers/               # API route controllers
|   |   |-- auth.py            # Register, login, SMS OTP, and Google OAuth
|   |   |-- campaigns.py       # CRUD operations, filters, and search
|   |   |-- donations.py       # Razorpay order creation, donate, webhook
|   |   |-- admin.py           # Admin review queue, metrics, donation ledger
|   |   `-- ai_assistant.py    # AI campaign generator and Q&A assistant
|   |-- schemas/               # Pydantic request and response schemas
|   `-- services/              # Business logic services
|       |-- ai_verifier.py     # AI scoring engine and Indian cost matrix
|       |-- payment_service.py # Razorpay integration, 80G receipts, fees
|       |-- sms_service.py     # Fast2SMS and Twilio SMS client
|       `-- google_auth_service.py # Google OAuth token verification
|-- frontend/
|   |-- src/
|   |   |-- app/
|   |   |   |-- animation/     # GSAP setup + scroll directives (reveal, split text, scrub text, count-up, parallax)
|   |   |   |-- components/    # Navbar, footer, campaign card, marquee, next-chapter link
|   |   |   |-- pages/         # Routed views: home, campaigns, campaign detail, how-it-works, trust, about, create, admin
|   |   |   `-- services/      # Angular services: auth, campaigns, donations, theme, smooth scroll (Lenis)
|   |   |-- index.html         # Fonts, theme bootstrap (no flash), Razorpay and Google GIS scripts
|   |   `-- styles.css         # Design tokens (light/dark "Saffron & Paper" theme) and base styles
|   |-- package.json
|   `-- angular.json
|-- tests/                     # Pytest automated test suite (17 tests)
|-- requirements.txt           # Python dependencies
|-- seed_data.py               # Database seeder with realistic Indian campaigns
|-- run.py                     # Backend development launcher
|-- .env.example               # Template environment configuration
`-- .gitignore                 # Git ignore rules for Python, Node, and secrets
```

---

## Getting Started

### Prerequisites

- Python 3.9 or higher
- Node.js 18 or higher and npm
- Git

### 1. Clone the Repository

```bash
git clone https://github.com/ArshSaharan/SevaFund.git
cd SevaFund
```

### 2. Environment Configuration

Copy the template environment file:

```bash
cp .env.example .env
```

Configure the following variables in `.env`:

- `DATABASE_URL`: Database connection string (defaults to `sqlite:///./crowdfund.db`).
- `SECRET_KEY`: A secure random string for JWT signing.
- `FAST2SMS_API_KEY`: API key from Fast2SMS (for Indian mobile OTPs).
- `GOOGLE_CLIENT_ID`: Google Cloud Web Client ID (Authorized JavaScript origin: `http://localhost:4200`).
- `RAZORPAY_KEY_ID`: Razorpay Test Key ID (leave blank to run in simulation mode).
- `RAZORPAY_KEY_SECRET`: Razorpay Test Key Secret.
- `GEMINI_API_KEY`: Google Gemini API key (optional; system includes offline heuristic verifier).

### 3. Backend Setup

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Seed sample Indian campaigns and test users
python seed_data.py

# Start FastAPI development server
python run.py
```

The backend server runs at `http://localhost:8000`. Interactive OpenAPI documentation is available at `http://localhost:8000/docs`.

### 4. Frontend Setup

In a separate terminal:

```bash
cd frontend

# Install Node dependencies
npm install

# Start Angular development server
npm start
```

The frontend application runs at `http://localhost:4200`.

---

## Seed Data and Test Accounts

Running `python seed_data.py` populates the database with realistic campaigns and test accounts:

- **Admin Account**:
  - Email: `admin@sevafund.org`
  - Password: `AdminPassword123!`
  - Role: Has full access to the Admin Dashboard and Donations Ledger at `/admin`.
- **Organizer Account**:
  - Email: `organizer@sevafund.org`
  - Password: `OrganizerPassword123!`
- **Sample Campaigns**:
  - Pediatric leukemia chemotherapy treatment at Tata Memorial Hospital, Mumbai.
  - Wayanad emergency flood relief and ration kits.
  - Knee replacement surgery estimate verification.
  - Flagged/rejected campaign for risk scoring demonstration.

---

## Running Automated Tests

The backend includes a comprehensive pytest suite covering authentication, AI verification scoring, campaign lifecycles, Razorpay order processing, and admin ledger permissions:

```bash
PYTHONPATH=. pytest tests/
```

All 17 tests validate business rules, 80G receipt number formats, fee calculations, and permission gates.

---

## API Endpoints Summary

### Authentication (`/api/auth`)
- `POST /register`: Register a new organizer or donor.
- `POST /login`: Authenticate with email/password and obtain JWT.
- `POST /send-otp`: Dispatch a 6-digit SMS OTP to an Indian mobile number.
- `POST /verify-otp`: Validate SMS OTP and authenticate.
- `POST /google`: Authenticate via Google OAuth 2.0 credential token.

### Campaigns (`/api/campaigns`)
- `GET /`: List active approved campaigns with search and category filters.
- `GET /{id}`: Retrieve campaign details, updates, documents, and donor list.
- `POST /`: Submit a new campaign for automated AI verification and review.
- `POST /{id}/donate`: Process a donation, verify signature, and issue 80G receipt.

### Donations (`/api/donations`)
- `POST /create-order`: Generate a Razorpay order in INR paise.
- `POST /webhook`: Handle Razorpay asynchronous payment capture webhooks.

### Administration (`/api/admin`)
- `GET /campaigns`: Review queue for pending, flagged, and active campaigns.
- `PUT /campaigns/{id}/review`: Approve, reject, or flag campaigns with notes.
- `GET /donations`: Audit ledger displaying donor identity, PAN, amounts, and beneficiary mapping.
- `GET /metrics`: Aggregated platform statistics.

---

## Security and Compliance

- Environment variables and database credentials are excluded from version control via `.gitignore`.
- Passwords are encrypted using bcrypt.
- Razorpay webhook signatures and payment signatures are validated using HMAC-SHA256.
- Admin endpoints require JWT tokens with the administrator role.
- Donor PAN numbers are secured and visible exclusively to authorized administrators for 80G statutory reporting.
