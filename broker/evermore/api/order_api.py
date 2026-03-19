# Evermore (AutoTradeTech) Order API
# All endpoints use POST with JSON body

import json
import os

from broker.evermore.api.auth_api import get_evermore_auth
from broker.evermore.mapping.transform_data import (
    map_exchange,
    map_product_type,
    reverse_map_exchange,
    reverse_map_product_type,
    transform_data,
    transform_modify_order_data,
)
from database.token_db import get_br_symbol, get_oa_symbol, get_token
from utils.httpx_client import get_httpx_client
from utils.logging import get_logger

logger = get_logger(__name__)


def _get_base_url():
    """Get Evermore REST API base URL from environment."""
    return os.getenv("EVERMORE_BASE_URL", "http://192.168.6.164:16006")


def _post_request(endpoint, payload):
    """
    Make a POST request to Evermore API.

    Args:
        endpoint: API endpoint path (e.g., '/api/PublicAPI/OrderEntry')
        payload: JSON payload dict

    Returns:
        dict: Parsed JSON response
    """
    base_url = _get_base_url()
    url = f"{base_url}{endpoint}"

    client = get_httpx_client()
    headers = {"Content-Type": "application/json"}

    try:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        error_msg = str(e)
        try:
            if hasattr(e, "response") and e.response is not None:
                error_detail = e.response.json()
                error_msg = error_detail.get("Error", str(e))
        except Exception:
            pass
        logger.exception(f"Evermore API request failed: {error_msg}")
        raise


def get_order_book(auth):
    """Fetch today's orders from Evermore."""
    creds = get_evermore_auth(auth)

    payload = {
        "UniqueId": creds["UniqueId"],
        "RefNo": creds["RefNo"],
        "Error": "",
    }

    try:
        response_data = _post_request("/api/PublicAPI/OrderBookRequest", payload)
        # Evermore returns a direct list. Wrap for consistent handling.
        if isinstance(response_data, list):
            return {"status": "success", "data": response_data}
        return response_data
    except Exception as e:
        logger.error(f"Error fetching order book: {e}")
        return {"status": "error", "data": None}


def get_trade_book(auth):
    """Fetch today's trades from Evermore."""
    creds = get_evermore_auth(auth)

    payload = {
        "UniqueId": creds["UniqueId"],
        "RefNo": creds["RefNo"],
        "Error": "",
    }

    try:
        response_data = _post_request("/api/PublicAPI/TradeBookRequest", payload)
        if isinstance(response_data, list):
            return {"status": "success", "data": response_data}
        return response_data
    except Exception as e:
        logger.error(f"Error fetching trade book: {e}")
        return {"status": "error", "data": None}


def get_positions(auth):
    """Fetch current positions from Evermore."""
    creds = get_evermore_auth(auth)

    payload = {
        "Uniqueid": creds["UniqueId"],  # Note: lowercase 'i' per Evermore API
        "RefNo": creds["RefNo"],
        "Error": "",
        "ClientCode": "",  # Empty for PRO account
    }

    try:
        response_data = _post_request("/api/PublicAPI/PositionRequest", payload)
        if isinstance(response_data, list):
            # Wrap in Zerodha-compatible structure for map_position_data
            return {"status": True, "data": {"net": response_data}}
        return response_data
    except Exception as e:
        logger.error(f"Error fetching positions: {e}")
        return {"status": False, "data": {"net": None}}


def get_holdings(auth):
    """
    Evermore does not provide a holdings API.
    Returns empty structure compatible with OpenAlgo.
    """
    return {"status": "success", "data": []}


def get_open_position(tradingsymbol, exchange, product, auth):
    """
    Get the net quantity of an open position for a specific symbol.
    """
    tradingsymbol = get_br_symbol(tradingsymbol, exchange)
    token = get_token(tradingsymbol, exchange)

    positions_data = get_positions(auth)
    net_qty = "0"

    if positions_data and positions_data.get("data"):
        position_list = positions_data["data"]
        if isinstance(position_list, dict) and "net" in position_list:
            position_list = position_list["net"]

        if position_list:
            for position in position_list:
                pos_token = str(position.get("TokenNo", ""))
                if pos_token == str(token):
                    net_qty = str(int(float(position.get("Qty", 0))))
                    logger.info(f"Net Quantity for {tradingsymbol}: {net_qty}")
                    break

    return net_qty


def place_order_api(data, auth):
    """
    Place a new order on Evermore.

    Args:
        data: OpenAlgo order data
        auth: JSON-encoded auth token

    Returns:
        tuple: (response_obj, response_data, orderid)
    """
    creds = get_evermore_auth(auth)
    newdata = transform_data(data)

    payload = {
        "Uniqueid": creds["UniqueId"],  # Note: lowercase 'i'
        "LoginId": creds["LoginId"],
        "RefNo": creds["RefNo"],
        "gateway": newdata["gateway"],
        "Exchange": newdata["Exchange"],
        "Tokenno": newdata["Tokenno"],
        "clientcode": "",  # Empty for PRO account
        "Buysell": newdata["Buysell"],
        "qty": newdata["qty"],
        "qtydisclosed": newdata["qtydisclosed"],
        "Price": newdata["Price"],
        "Triggerprice": newdata["Triggerprice"],
        "Booktype": newdata["Booktype"],
        "validity": newdata["validity"],
        "DeliveryType": newdata["DeliveryType"],
    }

    logger.info(f"Evermore place_order payload: {payload}")

    try:
        response_data = _post_request("/api/PublicAPI/OrderEntry", payload)
        logger.info(f"Evermore place_order response: {response_data}")

        int_ord_no = response_data.get("IntOrdNo", 0)
        error = response_data.get("Error")

        if int_ord_no and int_ord_no > 0:
            orderid = str(int_ord_no)
            result = {"status": "success", "orderid": orderid}
        else:
            orderid = None
            error_msg = error if error else "Order placement failed"
            result = {"status": "error", "message": error_msg}

        # Create a mock response object with status attribute for compatibility
        class MockResponse:
            def __init__(self, status_code):
                self.status = status_code
                self.status_code = status_code

        res = MockResponse(200 if orderid else 400)
        return res, result, orderid

    except Exception as e:
        logger.exception(f"Error placing order: {e}")

        class MockResponse:
            def __init__(self):
                self.status = 500
                self.status_code = 500

        return MockResponse(), {"status": "error", "message": str(e)}, None


def place_smartorder_api(data, auth):
    """
    Intelligent position management - calculates quantity based on desired position size.
    """
    AUTH_TOKEN = auth
    res = None
    response_data = {"status": "error", "message": "No action required or invalid parameters"}
    orderid = None

    try:
        symbol = data.get("symbol")
        exchange = data.get("exchange")
        product = data.get("product")

        if not all([symbol, exchange, product]):
            logger.info("Missing required parameters in place_smartorder_api")
            return res, response_data, orderid

        position_size = int(data.get("position_size", "0"))

        # Get current open position
        current_position = int(get_open_position(symbol, exchange, product, AUTH_TOKEN))

        logger.info(f"position_size: {position_size}")
        logger.info(f"Open Position: {current_position}")

        action = None
        quantity = 0

        if position_size == 0 and current_position > 0:
            action = "SELL"
            quantity = abs(current_position)
        elif position_size == 0 and current_position < 0:
            action = "BUY"
            quantity = abs(current_position)
        elif current_position == 0:
            action = "BUY" if position_size > 0 else "SELL"
            quantity = abs(position_size)
        else:
            if position_size > current_position:
                action = "BUY"
                quantity = position_size - current_position
            elif position_size < current_position:
                action = "SELL"
                quantity = current_position - position_size

        if action and quantity > 0:
            order_data = data.copy()
            order_data["action"] = action
            order_data["quantity"] = str(quantity)
            res, response, orderid = place_order_api(order_data, AUTH_TOKEN)
            return res, response, orderid
        else:
            logger.info("No action required or invalid quantity")
            response_data = {"status": "success", "message": "No action required"}
            return res, response_data, orderid

    except Exception as e:
        error_msg = f"Error in place_smartorder_api: {e}"
        logger.exception(error_msg)
        response_data = {"status": "error", "message": error_msg}
        return res, response_data, orderid


def modify_order(data, auth):
    """
    Modify an existing order on Evermore.

    Args:
        data: OpenAlgo modify order data (must include 'orderid')
        auth: JSON-encoded auth token

    Returns:
        tuple: (response_data, status_code)
    """
    creds = get_evermore_auth(auth)
    newdata = transform_modify_order_data(data)

    payload = {
        "Uniqueid": creds["UniqueId"],  # Note: lowercase 'i'
        "RefNo": creds["RefNo"],
        "IntordNo": int(data["orderid"]),  # Note: lowercase 'o'
        "qty": newdata["qty"],
        "qtydisclosed": newdata["qtydisclosed"],
        "Price": newdata["Price"],
        "TriggerPrice": newdata["TriggerPrice"],  # Note: capital T and P
        "Booktype": newdata["Booktype"],
        "Validity": newdata["Validity"],  # Note: capital V
    }

    logger.info(f"Evermore modify_order payload: {payload}")

    try:
        response_data = _post_request("/api/PublicAPI/ModifyRequest", payload)
        logger.info(f"Evermore modify_order response: {response_data}")

        int_ord_no = response_data.get("IntOrdNo", 0)
        error = response_data.get("Error")

        if int_ord_no and int_ord_no > 0:
            return {"status": "success", "orderid": str(int_ord_no)}, 200
        else:
            error_msg = error if error else "Failed to modify order"
            return {"status": "error", "message": error_msg}, 400

    except Exception as e:
        logger.exception(f"Error modifying order: {e}")
        return {"status": "error", "message": f"Failed to modify order: {str(e)}"}, 500


def cancel_order(orderid, auth):
    """
    Cancel an existing order on Evermore.

    Args:
        orderid: The IntOrdNo of the order to cancel
        auth: JSON-encoded auth token

    Returns:
        tuple: (response_data, status_code)
    """
    creds = get_evermore_auth(auth)

    payload = {
        "UniqueId": creds["UniqueId"],  # Note: capital 'I' for CancelRequest
        "RefNo": creds["RefNo"],
        "IntOrdNo": int(orderid),  # Note: capital 'O' for CancelRequest
    }

    logger.info(f"Evermore cancel_order payload: {payload}")

    try:
        response_data = _post_request("/api/PublicAPI/CancelRequest", payload)
        logger.info(f"Evermore cancel_order response: {response_data}")

        int_ord_no = response_data.get("IntOrdNo", 0)
        error = response_data.get("Error")

        if int_ord_no and int_ord_no > 0:
            return {"status": "success", "orderid": str(int_ord_no)}, 200
        else:
            error_msg = error if error else "Failed to cancel order"
            return {"status": "error", "message": error_msg}, 400

    except Exception as e:
        logger.exception(f"Error canceling order {orderid}: {e}")
        return {"status": "error", "message": f"Failed to cancel order: {str(e)}"}, 500


def cancel_all_orders_api(data, auth):
    """
    Cancel all open orders.
    Evermore has no batch cancel — loops through orderbook and cancels each.
    """
    AUTH_TOKEN = auth
    order_book_response = get_order_book(AUTH_TOKEN)

    if not order_book_response or order_book_response.get("status") == "error":
        return [], []

    orders = order_book_response.get("data", [])
    if not orders:
        return [], []

    # Filter orders that are open/pending
    orders_to_cancel = [
        order for order in orders
        if order.get("OrderStatus", "").lower() in ("submitted", "epending", "epending")
    ]

    canceled_orders = []
    failed_cancellations = []

    for order in orders_to_cancel:
        orderid = str(order.get("IntOrdNo", ""))
        if orderid and orderid != "0":
            cancel_response, status_code = cancel_order(orderid, AUTH_TOKEN)
            if status_code == 200:
                canceled_orders.append(orderid)
            else:
                failed_cancellations.append(orderid)

    return canceled_orders, failed_cancellations


def close_all_positions(current_api_key, auth):
    """
    Close all open positions by placing reverse orders.
    """
    AUTH_TOKEN = auth
    positions_response = get_positions(AUTH_TOKEN)

    if not positions_response or not positions_response.get("data"):
        return {"message": "No Open Positions Found"}, 200

    position_list = positions_response["data"]
    if isinstance(position_list, dict) and "net" in position_list:
        position_list = position_list["net"]

    if not position_list:
        return {"message": "No Open Positions Found"}, 200

    for position in position_list:
        qty = int(float(position.get("Qty", 0)))
        if qty == 0:
            continue

        action = "SELL" if qty > 0 else "BUY"
        quantity = abs(qty)

        token_no = str(position.get("TokenNo", ""))
        exchange = reverse_map_exchange(position.get("Exchange", ""))

        # Look up OA symbol
        symbol = get_oa_symbol(token_no, exchange) if token_no else token_no

        place_order_payload = {
            "apikey": current_api_key,
            "strategy": "Squareoff",
            "symbol": symbol,
            "action": action,
            "exchange": exchange,
            "pricetype": "MARKET",
            "product": reverse_map_product_type(exchange, position.get("DeliveryType", 0)),
            "quantity": str(quantity),
        }

        logger.info(f"Close position payload: {place_order_payload}")
        _, api_response, _ = place_order_api(place_order_payload, AUTH_TOKEN)
        logger.info(f"Close position response: {api_response}")

    return {"status": "success", "message": "All Open Positions SquaredOff"}, 200
