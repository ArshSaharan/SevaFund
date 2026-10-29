import os
import logging
import httpx
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

async def send_real_sms_otp(phone_number: str, otp_code: str) -> Dict[str, Any]:
    """
    Sends a real SMS OTP to an Indian mobile number.
    Supports Fast2SMS (India's leading DLT-ready OTP provider) and Twilio.
    Falls back gracefully with logging if no third-party SMS key is configured.
    """
    clean_10_digit = phone_number.replace("+91", "").replace(" ", "").strip()
    full_e164 = f"+91{clean_10_digit}"

    fast2sms_key = os.getenv("FAST2SMS_API_KEY", "").strip()
    twilio_sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
    twilio_token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
    twilio_phone = os.getenv("TWILIO_FROM_PHONE", "").strip()

    # 1. Option A: Fast2SMS (Indian Gateway)
    if fast2sms_key:
        try:
            url = "https://www.fast2sms.com/dev/bulkV2"
            headers = {
                "authorization": fast2sms_key,
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            # Step A1: Try dedicated DLT OTP route first
            payload_otp = {
                "variables_values": str(otp_code),
                "route": "otp",
                "numbers": clean_10_digit,
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, data=payload_otp, headers=headers)
                data = resp.json()
                if resp.status_code == 200 and data.get("return") is True:
                    logger.info(f"✅ Real SMS dispatched via Fast2SMS (OTP route) to {full_e164}: {data}")
                    return {"success": True, "provider": "Fast2SMS (OTP Route)", "details": data}

                # Step A2: If OTP route requires website verification (status 996), fallback to Quick SMS (route='q')
                logger.info(f"Fast2SMS OTP route response: {data}. Falling back to Quick SMS (route='q')...")
                payload_quick = {
                    "route": "q",
                    "message": f"Your SevaFund India verification code is {otp_code}. Valid for 5 minutes.",
                    "numbers": clean_10_digit
                }
                resp_q = await client.post(url, data=payload_quick, headers=headers)
                data_q = resp_q.json()
                if resp_q.status_code == 200 and data_q.get("return") is True:
                    logger.info(f"✅ Real SMS dispatched via Fast2SMS (Quick Route) to {full_e164}: {data_q}")
                    return {"success": True, "provider": "Fast2SMS", "details": data_q}
                else:
                    logger.error(f"❌ Fast2SMS Quick Route error: {data_q}")
                    return {"success": False, "provider": "Fast2SMS", "details": data_q}
        except Exception as e:
            logger.error(f"Failed to send SMS via Fast2SMS: {e}")
            return {"success": False, "provider": "Fast2SMS", "error": str(e)}

    # 2. Option B: Twilio
    if twilio_sid and twilio_token and twilio_phone:
        try:
            url = f"https://api.twilio.com/2010-04-01/Accounts/{twilio_sid}/Messages.json"
            data = {
                "To": full_e164,
                "From": twilio_phone,
                "Body": f"Your SevaFund India verification OTP is: {otp_code}. Valid for 5 minutes. Do not share this with anyone."
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, data=data, auth=(twilio_sid, twilio_token))
                if resp.status_code in (200, 201):
                    logger.info(f"✅ Real SMS sent via Twilio to {full_e164}")
                    return {"success": True, "provider": "Twilio"}
                else:
                    logger.error(f"❌ Twilio error: {resp.text}")
                    return {"success": False, "provider": "Twilio", "error": resp.text}
        except Exception as e:
            logger.error(f"Failed to send SMS via Twilio: {e}")
            return {"success": False, "provider": "Twilio", "error": str(e)}

    # 3. Fallback: Local Developer Simulation
    logger.info(f"📱 [DEV SMS SIMULATION] OTP for {full_e164}: {otp_code} (No SMS API Key configured in .env)")
    return {
        "success": True,
        "provider": "SIMULATION",
        "message": "Real SMS key not configured in .env; generated OTP available in dev response."
    }
