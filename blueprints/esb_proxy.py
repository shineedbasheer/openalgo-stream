"""
ESB Proxy Blueprint
Proxies requests from /esb/* to the Strategy Engine ESB service.
This avoids CORS issues when the React frontend calls the ESB API.
"""

import os

import requests
from flask import Blueprint, Response, request

esb_proxy_bp = Blueprint("esb_proxy", __name__)

ESB_BASE_URL = os.environ.get("ESB_BASE_URL", "http://192.168.6.176:6001")


@esb_proxy_bp.route("/esb/<path:path>", methods=["GET", "POST", "PUT", "DELETE"])
def proxy_esb(path):
    """Forward requests to the ESB service."""
    target_url = f"{ESB_BASE_URL}/esb/{path}"

    # Forward query parameters
    params = request.args.to_dict()

    # Forward headers (except host)
    headers = {
        key: value
        for key, value in request.headers
        if key.lower() not in ("host", "content-length")
    }

    try:
        resp = requests.request(
            method=request.method,
            url=target_url,
            params=params,
            headers=headers,
            data=request.get_data(),
            timeout=30,
        )

        # Build Flask response from upstream response
        response = Response(
            resp.content,
            status=resp.status_code,
            content_type=resp.headers.get("Content-Type", "application/json"),
        )

        return response

    except requests.exceptions.ConnectionError:
        return {"status": "error", "message": "ESB service unavailable"}, 502
    except requests.exceptions.Timeout:
        return {"status": "error", "message": "ESB service timeout"}, 504
