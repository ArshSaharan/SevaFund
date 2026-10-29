import json
import datetime
from app.database import SessionLocal, engine, Base
from app.models.user import User
from app.models.campaign import Campaign
from app.models.donation import Donation
from app.models.update import CampaignUpdate
from app.models.verification import VerificationAudit
from app.services.security import hash_password

def seed():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    print("🌱 Seeding Indian Crowdfunding Database (INR - ₹)...")

    # 1. Create Users
    priya = User(
        email="priya.sharma@example.com",
        phone_number="+919876543210",
        hashed_password=hash_password("password123"),
        full_name="Priya Sharma",
        role="USER",
        is_identity_verified=True,
        is_email_verified=True,
        is_phone_verified=True
    )
    rahul = User(
        email="rahul.verma@example.com",
        phone_number="+919812345678",
        hashed_password=hash_password("password123"),
        full_name="Rahul Verma",
        role="USER",
        is_identity_verified=True,
        is_email_verified=True,
        is_phone_verified=True
    )
    admin_user = User(
        email="admin@crowdfund-trust.in",
        phone_number="+919999988888",
        hashed_password=hash_password("admin123"),
        full_name="Vikram Mehta (Trust & Safety Lead)",
        role="ADMIN",
        is_identity_verified=True,
        is_email_verified=True,
        is_phone_verified=True
    )
    db.add_all([priya, rahul, admin_user])
    db.commit()
    db.refresh(priya)
    db.refresh(rahul)
    db.refresh(admin_user)

    # 2. Campaign 1: Genuine, High-Trust Indian Medical Campaign (Tata Memorial, Mumbai)
    docs_c1 = [
        {"doc_type": "HOSPITAL_ESTIMATE", "title": "Tata Memorial Hospital Official Estimate Letter", "file_url": "https://storage.example.com/docs/tmh-estimate-8812.pdf", "verified": True},
        {"doc_type": "AADHAAR", "title": "Parent Aadhaar Card Verified", "file_url": "https://storage.example.com/docs/aadhaar-verified.png", "verified": True}
    ]
    c1 = Campaign(
        creator_id=priya.id,
        title="Help 7-Year-Old Aarav Undergo Leukemia Chemotherapy at Tata Memorial Hospital",
        subtitle="Supporting chemotherapy cycles, blood transfusions, and sterile care for Aarav's cancer recovery in Mumbai.",
        category="MEDICAL",
        story="""Our 7-year-old son Aarav has been diagnosed with Acute Lymphoblastic Leukemia (ALL) at Tata Memorial Hospital in Mumbai (Patient UHID: TMH-2026-8812). Dr. Suresh Advani and his pediatric oncology team have outlined an intensive 18-month treatment plan.

We come from a middle-class family from Pune. We have already utilized our savings of ₹3,50,000 on initial ICU admissions and bone marrow biopsies. However, the total cost for multi-agent chemotherapy cycles, daily platelet transfusions, and sterile isolation care is estimated at ₹12,00,000 as per the official Tata Memorial estimate letter attached.

Fund Utilization Breakdown:
- ₹7,50,000: Chemotherapy medications, protocol injections, and surgical port insertion
- ₹2,50,000: Pediatric ICU bed stay and supportive blood/platelet transfusion bank fees
- ₹2,00,000: Post-chemo sterile nutrition, anti-fungal medicines, and diagnostic bone marrow scans

We will be posting hospital billing receipts after every single cycle. Every contribution through UPI or card goes directly towards saving our son's life. Please keep Aarav in your prayers.""",
        goal_amount=1200000.0,
        current_amount=845000.0,
        currency="INR",
        donor_count=320,
        cover_image_url="https://images.unsplash.com/photo-1579684385127-1ef15d508118?auto=format&fit=crop&w=1200&q=80",
        country="IN",
        state="Maharashtra",
        city="Mumbai",
        postal_code="400012",
        beneficiary_type="FAMILY",
        beneficiary_name="Aarav Sharma",
        relationship_to_beneficiary="Son",
        hospital_name="Tata Memorial Hospital, Parel, Mumbai",
        hospital_patient_uhid="TMH-2026-8812",
        is_80g_tax_exempt=True,
        direct_hospital_transfer=True,
        status="ACTIVE",
        proof_documents_json=json.dumps(docs_c1),
        authenticity_score=94.5,
        risk_level="LOW",
        ai_recommendation="AUTO_APPROVE",
        ai_verified_at=datetime.datetime.utcnow() - datetime.timedelta(days=10)
    )

    # 3. Campaign 2: Kerala Emergency Flood Relief (Wayanad, Kerala)
    docs_c2 = [
        {"doc_type": "NGO_REGISTRATION", "title": "Kerala District Disaster Relief Authorization", "file_url": "https://storage.example.com/kerala-collectorate-cert.pdf", "verified": True}
    ]
    c2 = Campaign(
        creator_id=rahul.id,
        title="Emergency Flood Relief & Food Ration Kits for 200 Families in Wayanad",
        subtitle="Direct relief kit distribution including dry food rations, drinking water, and clean bedding in flood-hit areas.",
        category="EMERGENCY",
        story="""Due to relentless monsoon landslides and flash floods in Wayanad, over 200 families have been displaced into community shelters. Local volunteers are preparing dry ration emergency kits.

Each kit costs ₹2,500 and provides a family of 4 with:
- Rice, Dal, Cooking Oil, Salt, Spices (20 days supply)
- Water purification tablets & solar lamps
- Clean blankets and hygiene sanitary kits

Target Goal: ₹5,00,000 for 200 families.
All purchases are being made with GST bills from local wholesale suppliers. Regular distribution photos and ration registers will be updated daily.""",
        goal_amount=500000.0,
        current_amount=380000.0,
        currency="INR",
        donor_count=195,
        cover_image_url="https://images.unsplash.com/photo-1544717305-2782549b5136?auto=format&fit=crop&w=1200&q=80",
        country="IN",
        state="Kerala",
        city="Wayanad",
        postal_code="673121",
        beneficiary_type="COMMUNITY",
        beneficiary_name="Wayanad Disaster Relief Collective",
        relationship_to_beneficiary="Community Organizer",
        is_80g_tax_exempt=True,
        direct_hospital_transfer=False,
        status="ACTIVE",
        proof_documents_json=json.dumps(docs_c2),
        authenticity_score=89.0,
        risk_level="LOW",
        ai_recommendation="AUTO_APPROVE",
        ai_verified_at=datetime.datetime.utcnow() - datetime.timedelta(days=4)
    )

    # 4. Campaign 3: Flagged / Borderline Review (Needs Hospital Estimate)
    c3 = Campaign(
        creator_id=priya.id,
        title="Emergency Knee Surgery Fund for Neighbor",
        subtitle="Raising money for knee surgery in Lucknow.",
        category="MEDICAL",
        story="""My neighbor uncle has severe knee pain and needs surgery done quickly. The surgery is expensive and he has no Ayushman card. Please donate money quickly so we can get it done.""",
        goal_amount=400000.0,
        current_amount=0.0,
        currency="INR",
        donor_count=0,
        cover_image_url="https://images.unsplash.com/photo-1516549655169-df83a0774514?auto=format&fit=crop&w=1200&q=80",
        country="IN",
        state="Uttar Pradesh",
        city="Lucknow",
        postal_code="226001",
        beneficiary_type="FRIEND",
        beneficiary_name="",
        relationship_to_beneficiary="Neighbor",
        status="FLAGGED",
        proof_documents_json=None,
        authenticity_score=48.0,
        risk_level="HIGH",
        ai_recommendation="FLAG_FOR_REVIEW",
        ai_verified_at=datetime.datetime.utcnow() - datetime.timedelta(days=1)
    )

    # 5. Campaign 4: Scam Pattern (Personal UPI, Fake Ayurvedic Miracle Cure)
    c4 = Campaign(
        creator_id=rahul.id,
        title="SECRET BABAJI AYURVEDIC CANCER CURE - GPAY / PHONEPE DIRECTLY",
        subtitle="100% guarantee cure for all cancer stages without any doctor or surgery.",
        category="MEDICAL",
        story="""Send money right this second directly to my personal GooglePay and PhonePe number! Doctors hate this secret remedy that guarantees 100% cure for cancer in 3 days. Send ₹90,00,000 immediately, do not ask any questions or ask for hospital bills.""",
        goal_amount=9000000.0,
        current_amount=0.0,
        currency="INR",
        donor_count=0,
        cover_image_url=None,
        country="IN",
        state="Delhi",
        city="New Delhi",
        postal_code="110001",
        beneficiary_type="SELF",
        beneficiary_name="Unknown",
        relationship_to_beneficiary="Self",
        status="REJECTED",
        proof_documents_json=None,
        authenticity_score=11.0,
        risk_level="CRITICAL",
        ai_recommendation="REJECT",
        ai_verified_at=datetime.datetime.utcnow()
    )

    db.add_all([c1, c2, c3, c4])
    db.commit()
    db.refresh(c1)
    db.refresh(c2)
    db.refresh(c3)
    db.refresh(c4)

    # Add realistic Indian UPI, Razorpay & card donations with complete donor identity
    donations_data = [
        {"campaign_id": c1.id, "donor_name": "Aditya Kulkarni", "email": "aditya.kulkarni@gmail.com", "phone": "+919820011223", "amount": 5000.0, "tip": 200.0, "method": "RAZORPAY", "upi_id": "aditya@okaxis", "pan": "ABCDE1234F", "msg": "Praying for little Aarav's complete recovery!", "anon": False},
        {"campaign_id": c1.id, "donor_name": "Meera Swaminathan", "email": "meera.s@example.com", "phone": "+919845012345", "amount": 25000.0, "tip": 1000.0, "method": "NETBANKING", "upi_id": None, "pan": "XYZPK9988M", "msg": "Stay strong Priya. Sending support from Bangalore.", "anon": True},
        {"campaign_id": c1.id, "donor_name": "Dr. Sneha Roy", "email": "sneha.roy@aiims.edu", "phone": "+919811099887", "amount": 2000.0, "tip": 100.0, "method": "UPI", "upi_id": "sneha@paytm", "pan": None, "msg": "Tata Memorial has the best doctors. Aarav will be fine!", "anon": False},
        {"campaign_id": c1.id, "donor_name": "Kavita Nair", "email": "kavita.nair@example.com", "phone": "+919895044332", "amount": 10000.0, "tip": 500.0, "method": "UPI", "upi_id": "kavita@ybl", "pan": "KAVIN8765L", "msg": "May God bless Aarav with good health.", "anon": False},
        {"campaign_id": c2.id, "donor_name": "Rajeshwari Iyer", "email": "rajeshwari.iyer@gmail.com", "phone": "+919821033445", "amount": 15000.0, "tip": 500.0, "method": "RAZORPAY", "upi_id": "rajeshwari@icici", "pan": "RAJES5544K", "msg": "Standing with the families of Wayanad. Hope ration kits reach promptly.", "anon": False},
        {"campaign_id": c2.id, "donor_name": "Tariq Mansoor", "email": "tariq.mansoor@example.com", "phone": "+919871022334", "amount": 7500.0, "tip": 250.0, "method": "UPI", "upi_id": "tariq@okaxis", "pan": None, "msg": "May peace and relief return to the valley soon.", "anon": True},
    ]

    for idx, d in enumerate(donations_data):
        receipt_80g = f"80G-2026-00{idx+1}{d['pan'][:4]}" if d["pan"] else None
        don = Donation(
            campaign_id=d["campaign_id"],
            donor_name=d["donor_name"],
            donor_email=d["email"],
            donor_phone=d["phone"],
            donor_pan=d["pan"],
            amount=d["amount"],
            tip_amount=d["tip"],
            fee_amount=0.0 if d["method"] == "UPI" else round(d["amount"] * 0.0236, 2),
            net_amount=d["amount"],
            currency="INR",
            payment_method=d["method"],
            upi_id=d["upi_id"],
            tax_exemption_80g_number=receipt_80g,
            support_message=d["msg"],
            is_anonymous=d["anon"],
            payment_status="COMPLETED",
            transaction_ref=f"TXN-IN-20261028-000{idx+1}A",
            gateway_order_id=f"order_seed_{idx+1}",
            gateway_payment_id=f"pay_seed_{idx+1}"
        )
        db.add(don)

    # Add milestone update
    u1 = CampaignUpdate(
        campaign_id=c1.id,
        title="Aarav Finished Cycle 1 Chemotherapy at Tata Memorial!",
        content="Dear supporters, Aarav tolerated his first induction chemo cycle well. Dr. Advani mentioned his blast cell count is dropping. Thank you all for your heartfelt blessings and UPI contributions!",
        image_url="https://images.unsplash.com/photo-1584515979956-d9f6e5d09982?auto=format&fit=crop&w=800&q=80",
        created_at=datetime.datetime.utcnow() - datetime.timedelta(days=3)
    )
    db.add(u1)

    db.commit()
    print("✅ Seed completed successfully! Created realistic Indian campaigns (Tata Memorial, Kerala Relief, etc.) in INR (₹).")
    db.close()

if __name__ == "__main__":
    seed()
