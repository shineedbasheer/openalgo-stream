# Mapping OpenAlgo API Authentication
# Mapping Evermore (AutoTradeTech) Login API

import json
import os

from utils.httpx_client import get_httpx_client
from utils.logging import get_logger

logger = get_logger(__name__)


def authenticate_broker(request_token):
    """
    Authenticate with the Evermore (AutoTradeTech) broker API.

    Evermore uses a simple LoginId + Password authentication flow.
    - LoginId comes from BROKER_API_KEY env var
    - Password comes from BROKER_API_SECRET env var
    - request_token is not used for OAuth (Evermore has no OAuth flow)

    Returns a JSON-encoded auth token containing UniqueId and RefNo.
    """
    try:
        LOGIN_ID = os.getenv("BROKER_API_KEY")
        PASSWORD = os.getenv("BROKER_API_SECRET")
        BASE_URL = os.getenv("EVERMORE_BASE_URL", "http://192.168.6.164:16006")

        if not LOGIN_ID or not PASSWORD:
            return None, "BROKER_API_KEY (LoginId) and BROKER_API_SECRET (Password) must be set in .env"

        url = f"{BASE_URL}/api/PublicAPI/LoginRequest"

        payload = {
            "LoginId": LOGIN_ID,
            "Password": PASSWORD,
        }

        # Get the shared httpx client with connection pooling
        client = get_httpx_client()

        headers = {"Content-Type": "application/json"}

        try:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()

            response_data = response.json()
            logger.info(f"Evermore login response: UniqueId={response_data.get('UniqueId')}")

            unique_id = response_data.get("UniqueId", 0)
            ref_no = response_data.get("RefNo", "")
            error = response_data.get("Error")

            if unique_id > 0 and ref_no:
                # Store both UniqueId and RefNo as JSON-encoded auth token
                auth_token = json.dumps({
                    "UniqueId": unique_id,
                    "RefNo": ref_no,
                    "LoginId": LOGIN_ID,
                })
                return auth_token, None
            else:
                error_msg = error if error else "Login failed: UniqueId=0 or RefNo empty"
                return None, f"Evermore authentication failed: {error_msg}"

        except Exception as e:
            error_message = str(e)
            try:
                if hasattr(e, "response") and e.response is not None:
                    error_detail = e.response.json()
                    error_message = error_detail.get("Error", str(e))
            except Exception:
                pass
            return None, f"API error: {error_message}"

    except Exception as e:
        return None, f"An exception occurred: {str(e)}"


def get_evermore_auth(auth_token):
    """
    Parse the JSON-encoded auth token to extract Evermore credentials.

    Returns:
        dict with keys: UniqueId (int), RefNo (str), LoginId (str)
    """
    try:
        return json.loads(auth_token)
    except (json.JSONDecodeError, TypeError):
        logger.error("Failed to parse Evermore auth token")
        return {"UniqueId": 0, "RefNo": "", "LoginId": ""}
