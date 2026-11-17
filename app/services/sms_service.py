import os
import logging
import httpx
from typing import Dict, Any

logger = logging.getLogger(__name__)

# OTP codes and provider response bodies are never written to logs or returned to callers.
_PLACEHOLDER_PREFIXES = ("your", "replace", "change", "xxx", "<")


def _configured(value: str) -> bool:
    value = (value or "").strip()
    return bool(value) and not value.lower().startswith(_PLACEHOLDER_PREFIXES)


def sms_configured() -> bool:
    """True when an SMS provider is configured (Fast2SMS key, or the full Twilio trio).  Configured does not
    guarantee delivery (for example, exhausted credits); a failed send is reported as unavailable."""
    if _configured(os.getenv("FAST2SMS_API_KEY", "")):
        return True
    return all(_configured(os.getenv(name, "")) for name in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM_PHONE"))


def _masked(e164: str) -> str:
    return f"{e164[:3]}******{e164[-4:]}" if len(e164) > 7 else "***"


async def send_real_sms_otp(phone_number: str, otp_code: str) -> Dict[str, Any]:
    """
    Sends an SMS OTP to an Indian mobile number through Fast2SMS or Twilio.
    Returns only {"success": bool, "provider": str}.  Without a configured provider nothing is sent
    (provider "SIMULATION", success False) and the caller must treat phone sign-in as unavailable.
    """
    clean_10_digit = phone_number.replace("+91", "").replace(" ", "").strip()
    full_e164 = f"+91{clean_10_digit}"

    fast2sms_key = os.getenv("FAST2SMS_API_KEY", "").strip()
    twilio_sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
    twilio_token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
    twilio_phone = os.getenv("TWILIO_FROM_PHONE", "").strip()

    # 1. Option A: Fast2SMS (Indian Gateway)
    if _configured(fast2sms_key):
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
                    logger.info("SMS OTP dispatched via Fast2SMS (OTP route) to %s", _masked(full_e164))
                    return {"success": True, "provider": "Fast2SMS (OTP Route)"}

                # Step A2: If the OTP route is not enabled for this account, fall back to Quick SMS (route='q')
                logger.info("Fast2SMS OTP route refused (HTTP %s); trying Quick SMS route", resp.status_code)
                payload_quick = {
                    "route": "q",
                    "message": f"Your SevaFund India verification code is {otp_code}. Valid for 5 minutes.",
                    "numbers": clean_10_digit
                }
                resp_q = await client.post(url, data=payload_quick, headers=headers)
                data_q = resp_q.json()
                if resp_q.status_code == 200 and data_q.get("return") is True:
                    logger.info("SMS OTP dispatched via Fast2SMS (Quick route) to %s", _masked(full_e164))
                    return {"success": True, "provider": "Fast2SMS"}
                logger.error("Fast2SMS Quick route failed (HTTP %s)", resp_q.status_code)
                return {"success": False, "provider": "Fast2SMS"}
        except Exception as e:
            logger.error("Failed to send SMS via Fast2SMS: %s", type(e).__name__)
            return {"success": False, "provider": "Fast2SMS"}

    # 2. Option B: Twilio
    if _configured(twilio_sid) and _configured(twilio_token) and _configured(twilio_phone):
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
                    logger.info("SMS OTP sent via Twilio to %s", _masked(full_e164))
                    return {"success": True, "provider": "Twilio"}
                logger.error("Twilio send failed (HTTP %s)", resp.status_code)
                return {"success": False, "provider": "Twilio"}
        except Exception as e:
            logger.error("Failed to send SMS via Twilio: %s", type(e).__name__)
            return {"success": False, "provider": "Twilio"}

    # 3. No provider configured: nothing is sent, and the code is not logged.
    logger.warning("No SMS provider configured; phone verification is unavailable")
    return {"success": False, "provider": "SIMULATION"}
