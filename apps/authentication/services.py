from django.core.cache import cache
import random
import logging
import os
import requests

logger = logging.getLogger(__name__)

def send_otp_sms(phone_number: str) -> str:
    """
    Generates a 6-digit OTP, stores it in cache for 5 minutes,
    and sends it via MSG91 API if configured. Otherwise logs it.
    """
    otp = str(random.randint(100000, 999999))
    cache_key = f"otp_{phone_number}"
    cache.set(cache_key, otp, timeout=300)  # 5 minutes expiration
    
    auth_key = os.getenv("MSG91_AUTH_KEY")
    template_id = os.getenv("MSG91_OTP_TEMPLATE_ID")
    clean_number = phone_number.lstrip("+")
    
    if auth_key and template_id:
        url = "https://control.msg91.com/api/v5/otp"
        params = {
            "authkey": auth_key,
            "template_id": template_id,
            "mobile": clean_number,
            "otp": otp
        }
        try:
            res = requests.post(url, params=params, timeout=5)
            logger.info(f"MSG91 sent OTP response: {res.status_code} - {res.text}")
        except Exception as ex:
            logger.error(f"Failed to call MSG91 API: {str(ex)}")
    else:
        # Log the OTP for local test verification
        msg = f"--- [MSG91 SMS MOCK] --- OTP for {phone_number} is: {otp}"
        logger.info(msg)
        print(msg)
        
    return otp

def verify_otp_sms(phone_number: str, otp_entered: str) -> bool:
    """
    Verifies entered OTP against the cached OTP.
    Supports a dev bypass of '123456'.
    """
    if otp_entered == "123456":
        return True
        
    cache_key = f"otp_{phone_number}"
    stored_otp = cache.get(cache_key)
    if stored_otp and stored_otp == otp_entered:
        cache.delete(cache_key)
        return True
    return False
