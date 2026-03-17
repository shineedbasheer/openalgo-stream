import json
import os

from utils.httpx_client import get_httpx_client
from utils.logging import get_logger

logger = get_logger(__name__)

# Evermore REST API base URL
# The PDF doc references ../api/PublicAPI/{method}
# Actual base URL should be configured via env var
DEFAULT_API_URL = "https://feedapi.com"


def get_api_url():
    """Get Evermore REST API base URL from environment"""
    return os.getenv("EVERMORE_API_URL", DEFAULT_API_URL)


def authenticate_broker(login_id, password, totp_code=None):
    """
    Authenticate with Evermore broker via LoginRequest API.

    Evermore uses LoginId + Password authentication.
    Returns UniqueId and RefNo which are needed for all subsequent API calls.

    The auth token is stored as "UniqueId:RefNo" format.
    The feed token stores "LoginId:Password" for the streaming WebSocket.

    Args:
        login_id: Evermore Login ID
        password: Evermore Password
        totp_code: Not used by Evermore (kept for interface compatibility)

    Returns:
        (auth_token, feed_token, error_message)
    """
    try:
        client = get_httpx_client()

        base_url = get_api_url()
        url = f"{base_url}/api/PublicAPI/LoginRequest"

        payload = json.dumps({
            "LoginId": login_id,
            "Password": password,
        })

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        response = client.post(url, headers=headers, content=payload)
        response.status = response.status_code

        if response.status_code != 200:
            return None, None, f"HTTP {response.status_code}: {response.text}"

        data = response.json()

        error = data.get("Error", "")
        if error:
            logger.error(f"Evermore login failed: {error}")
            return None, None, f"Login failed: {error}"

        unique_id = data.get("UniqueId")
        ref_no = data.get("RefNo")

        if unique_id is None or not ref_no:
            return None, None, "Login response missing UniqueId or RefNo"

        # Store auth as "UniqueId:RefNo" — both needed for every API call
        auth_token = f"{unique_id}:{ref_no}"

        # Feed token stores credentials for WebSocket streaming
        # The streaming adapter expects "login_id:password" format
        feed_token = f"{login_id}:{password}"

        logger.info(f"Evermore login successful. UniqueId={unique_id}")
        return auth_token, feed_token, None

    except Exception as e:
        logger.error(f"Evermore authentication error: {e}")
        return None, None, str(e)


def parse_auth_token(auth_token):
    """
    Parse the stored auth token into UniqueId and RefNo.

    Args:
        auth_token: Stored as "UniqueId:RefNo"

    Returns:
        (unique_id, ref_no) tuple
    """
    parts = auth_token.split(":", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid Evermore auth token format: expected 'UniqueId:RefNo'")
    return int(parts[0]), parts[1]
