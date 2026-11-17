"""Demonstrate hybrid v4 inside the SevaFund application (development flag), end to end, offline.

    python evaluation/final_evaluation/demo_app_integration.py

Runs the real FastAPI app in-process against a TEMPORARY SQLite database and upload folder (your crowdfund.db and
uploads/ are not touched), with SEVAFUND_DEV_HYBRID_V4=1, an offline scripted Gemini stand-in and GEMINI_API_KEY="".
External confirmations are SIMULATED by an admin recording them; nothing is contacted and no API is called.
Donations are paid through a DEMO-ONLY simulated Razorpay installed in this process (the application itself has no
payment simulation: without real Razorpay credentials it refuses to create orders or record donations).
"""
import datetime
import os
import sys
import tempfile
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix="sevafund-hybrid-v4-demo-"))
os.environ.update({"DATABASE_URL": f"sqlite:///{TMP / 'demo.db'}", "GEMINI_API_KEY": "", "SEVAFUND_DEV_HYBRID_V4": "1",
                   "SEVAFUND_DEV_HYBRID_V4_GEMINI": "mock-approve"})
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evaluation"))

from fastapi.testclient import TestClient  # noqa: E402

import app.routers.documents as documents  # noqa: E402
import app.services.rag as rag  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.security import create_access_token, hash_password  # noqa: E402
from independent_v5.preseal import NetworkGuard  # noqa: E402

(TMP / "uploads").mkdir()
rag.UPLOAD_DIR = documents.UPLOAD_DIR = TMP / "uploads"


class DemoRazorpay:
    """DEMO ONLY: an in-process stand-in for Razorpay's servers.  Creates orders, simulates the donor's checkout and
    signs the payment with a throwaway secret, so the real server-side verification can be shown.  No money moves."""

    def __init__(self):
        import secrets
        self.key_id, self.key_secret = "rzp_test_demosimulation", secrets.token_hex(24)
        self.orders, self.payments = {}, {}

    def create_order(self, amount_paise, currency, receipt, notes):
        import secrets
        order_id = "order_" + secrets.token_hex(7)
        self.orders[order_id] = {"id": order_id, "amount": amount_paise, "currency": currency}
        return dict(self.orders[order_id])

    def fetch_payment(self, payment_id):
        return dict(self.payments[payment_id])

    def pay(self, order_id):
        import secrets
        from app.services.payment_service import payment_signature
        payment_id = "pay_" + secrets.token_hex(7)
        order = self.orders[order_id]
        self.payments[payment_id] = {"id": payment_id, "order_id": order_id, "amount": order["amount"],
                                     "currency": order["currency"], "status": "captured"}
        return {"gateway_order_id": order_id, "gateway_payment_id": payment_id,
                "gateway_signature": payment_signature(order_id, payment_id, self.key_secret)}


def install_demo_razorpay() -> DemoRazorpay:
    import importlib
    from app.config import settings
    demo = DemoRazorpay()
    settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET = demo.key_id, demo.key_secret
    importlib.import_module("app.services.payment_service").get_gateway = lambda: demo
    return demo
TODAY = datetime.datetime.utcnow().date()


def d(days):
    return (TODAY + datetime.timedelta(days=days)).strftime("%d/%m/%Y")


def make_user(email, role):
    db = SessionLocal()
    u = User(email=email, hashed_password=hash_password("demo-only"), full_name=email.split("@")[0], role=role,
             is_identity_verified=True)
    db.add(u)
    db.commit()
    db.refresh(u)
    db.close()
    return {"Authorization": f"Bearer {create_access_token({'sub': str(u.id), 'role': role})}"}


def say(text):
    print(f"  {text}")


def main():
    client = TestClient(app)
    creator, admin = make_user("organiser@demo.local", "USER"), make_user("admin@demo.local", "ADMIN")

    def upload(title, text, doc_type):
        return client.post("/api/documents/upload", headers=creator, data={"doc_type": doc_type, "title": title},
                           files={"file": (f"{title}.txt", text.encode(), "text/plain")}).json()

    def create(title, goal, story, docs, name, city, state):
        return client.post("/api/campaigns", headers=creator, json={
            "title": title, "category": "MEDICAL", "goal_amount": goal, "story": story, "beneficiary_name": name,
            "city": city, "state": state, "proof_documents": docs}).json()

    def record(cid):
        return client.get(f"/api/dev/hybrid-v4/campaigns/{cid}", headers=admin).json()

    def confirm(cid, check, source, outcome="CONFIRMED", **extra):
        r = client.post(f"/api/dev/hybrid-v4/campaigns/{cid}/confirmations", headers=admin,
                        json={"check": check, "outcome": outcome, "contact_source": source, **extra}).json()
        say(f"confirm {check:<19} via {source:<18} {outcome:<11} -> campaign {r['campaign_status']}, "
            f"pending {r['activation']['pending_checks'] or 'none'}")
        return r

    razorpay = install_demo_razorpay()

    def donate(cid):
        """Order -> simulated checkout -> server-side verification.  Reports the first refusal."""
        r = client.post("/api/donations/create-order", json={"campaign_id": cid, "amount": 2500})
        if r.status_code == 200:
            r = client.post(f"/api/campaigns/{cid}/donate",
                            json={"amount": 2500, "payment_method": "UPI", **razorpay.pay(r.json()["order_id"])})
        say(f"donation attempt -> HTTP {r.status_code}" + (f" ({r.json().get('detail')})" if r.status_code != 201 else ""))

    def identity_checks(cid):
        confirm(cid, "BENEFICIARY", "PLATFORM_KYC")
        confirm(cid, "INSTITUTION", "OFFICIAL_DIRECTORY")
        confirm(cid, "PAYMENT_DESTINATION", "PLATFORM_KYC")

    estimate = ("Sushruta Hospital, Wardha Road, Nagpur 440015. Estimate No. SH/EST/26/4471 Date: {issued}\nPatient: "
                "Kamala Bai, 68 F, UHID SH-208813\nProcedure: Left hip hemiarthroplasty\nImplant Rs 75,000; Surgery and OT "
                "Rs 55,000; Ward 4 days Rs 32,000; Medicines Rs 23,000\nTotal estimate Rs {total}. Planned surgery date: "
                "{surgery}. Billing Executive (signed)")
    note = (f"Sushruta Hospital casualty {d(-4)}. Kamala Bai 68 F. Displaced fracture neck of left femur after a fall. "
            "Advised hemiarthroplasty. Dr P. Wankhede MS Ortho")
    story = "Kamala Bai, 68, fractured her left hip. Sushruta Hospital will operate next week."

    print("\n1. Genuine campaign: a high production score does not publish it; four confirmations do")
    docs = [upload("Hospital estimate", estimate.format(issued=d(-3), total="1,85,000", surgery=d(7)), "HOSPITAL_ESTIMATE"),
            upload("Orthopaedic note", note, "CLINICAL_NOTE")]
    c = create("Hip surgery for Kamala Bai", 185000, story, docs, "Kamala Bai", "Nagpur", "Maharashtra")
    r = record(c["id"])
    say(f"created: status {c['status']}, production score {c['authenticity_score']}, hybrid v4 {r['automated_decision']} "
        f"-> {r['workflow_state']}")
    a = client.post(f"/api/admin/campaigns/{c['id']}/decision", headers=admin, json={"decision": "APPROVE"})
    say(f"admin APPROVE -> HTTP {a.status_code} ({a.json()['detail'][:70]}...)")
    donate(c["id"])
    identity_checks(c["id"])
    donate(c["id"])
    r = confirm(c["id"], "AMOUNT", "OFFICIAL_DIRECTORY", stated_amount_inr=185000)
    say(f"disbursement limit Rs {r['activation']['disbursement_limit_inr']:,.0f}; audit chain valid "
        f"{r['activation']['audit_chain_valid']}")
    donate(c["id"])

    print("\n2. Consistent documents, inflated goal: stopped by the hospital billing desk's own figure")
    docs = [upload("Hospital estimate", estimate.format(issued=d(-3), total="3,00,000", surgery=d(7)), "HOSPITAL_ESTIMATE"),
            upload("Orthopaedic note", note, "CLINICAL_NOTE")]
    c = create("Hip surgery and rehabilitation for Kamala Bai", 300000, story, docs, "Kamala Bai", "Nagpur", "Maharashtra")
    say(f"created: status {c['status']}, hybrid v4 {record(c['id'])['workflow_state']}")
    identity_checks(c["id"])
    confirm(c["id"], "AMOUNT", "OFFICIAL_DIRECTORY", stated_amount_inr=185000)
    donate(c["id"])

    print("\n3. Genuine patient without a formal quotation: information request, assisted route, four confirmations")
    os.environ["SEVAFUND_DEV_HYBRID_V4_GEMINI"] = "mock-nmi"
    docs = [upload("List of items to purchase", "Government Medical College Hospital, Patna. Patient Bhola Prasad 39 M. "
                   f"Items to be purchased before surgery: pedicle screws 6, rods 2. Date {d(-6)}. Unit In-charge",
                   "HOSPITAL_LETTER"),
            upload("Admission slip", f"GMCH Patna. Admitted {d(-7)}. Bhola Prasad 39 M. L1 burst fracture. Planned "
                   "posterior fixation. Dr A. K. Singh", "CLINICAL_NOTE")]
    c = create("Spine surgery at the government hospital for Bhola", 120000,
               "Bhola Prasad injured his spine. The government hospital operates free but he must buy implants.",
               docs, "Bhola Prasad", "Patna", "Bihar")
    r = record(c["id"])
    say(f"created: status {c['status']}, hybrid v4 {r['workflow_state']}, route {r['manual_route']}")
    say(f"request: {r['information_requests'][-1][:110]}...")
    donate(c["id"])
    a = client.post(f"/api/dev/hybrid-v4/campaigns/{c['id']}/assisted-cost-review", headers=admin, json={}).json()
    say(f"caseworker starts assisted cost review -> {a['workflow_state']}, checks {a['required_checks']}")
    identity_checks(c["id"])
    confirm(c["id"], "AMOUNT", "OFFICIAL_DIRECTORY", stated_amount_inr=118000)
    donate(c["id"])
    print(f"\nTemporary database and uploads: {TMP}")


if __name__ == "__main__":
    print("Hybrid v4 development integration demo (offline; scripted Gemini; SIMULATED confirmations)")
    with NetworkGuard() as guard:
        main()
    print(f"Network connections attempted: {len(guard.attempts)}")
