import json
import os

from broker.evermore.api.auth_api import get_api_url, parse_auth_token
from broker.evermore.mapping.transform_data import (
    map_product_type,
    reverse_map_exchange,
    reverse_map_product_type_with_exchange,
    transform_data,
    transform_modify_order_data,
)
from database.token_db import get_symbol, get_token
from utils.httpx_client import get_httpx_client
from utils.logging import get_logger

logger = get_logger(__name__)


def _get_headers():
    """Standard headers for Evermore API requests"""
    return {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _make_request(endpoint, auth, extra_data=None):
    """
    Make an authenticated request to Evermore REST API.

    All Evermore API calls require UniqueId and RefNo from login.

    Args:
        endpoint: API method name (e.g., "OrderEntry", "OrderBookRequest")
        auth: Auth token in "UniqueId:RefNo" format
        extra_data: Additional fields to include in the request body

    Returns:
        Parsed JSON response dict
    """
    unique_id, ref_no = parse_auth_token(auth)
    client = get_httpx_client()

    base_url = get_api_url()
    url = f"{base_url}/api/PublicAPI/{endpoint}"

    payload = {
        "UniqueId": unique_id,
        "RefNo": ref_no,
    }
    if extra_data:
        payload.update(extra_data)

    try:
        response = client.post(url, headers=_get_headers(), content=json.dumps(payload))
        response.status = response.status_code

        if not response.text:
            return {}

        return json.loads(response.text)
    except json.JSONDecodeError:
        logger.error(f"Failed to parse JSON from {endpoint}: {response.text}")
        return {}
    except Exception as e:
        logger.error(f"Request to {endpoint} failed: {e}")
        return {}


def get_order_book(auth):
    """Fetch order book from Evermore"""
    return _make_request("OrderBookRequest", auth)


def get_trade_book(auth):
    """Fetch trade book from Evermore"""
    return _make_request("TradeBookRequest", auth)


def get_positions(auth):
    """Fetch positions from Evermore"""
    return _make_request("PositionRequest", auth)


def get_holdings(auth):
    """
    Fetch holdings from Evermore.

    NOTE: Evermore REST API doc does not include a holdings endpoint.
    Returns empty data structure for compatibility.
    """
    logger.warning("Evermore does not provide a holdings API")
    return {"status": False, "data": None, "message": "Holdings API not available for Evermore"}


def get_open_position(tradingsymbol, exchange, product_type, auth):
    """
    Get net quantity for a specific open position.

    Args:
        tradingsymbol: OpenAlgo symbol
        exchange: OpenAlgo exchange code
        product_type: Evermore DeliveryType (0 or 1)
        auth: Auth token

    Returns:
        Net quantity as string
    """
    token = get_token(tradingsymbol, exchange)
    positions_data = get_positions(auth)

    logger.debug(f"Positions response: {positions_data}")

    net_qty = "0"

    if positions_data and isinstance(positions_data, list):
        for position in positions_data:
            pos_token = str(position.get("TokenNo", ""))
            if pos_token == str(token):
                net_qty = str(position.get("Qty", 0))
                break
    elif positions_data and isinstance(positions_data, dict):
        # Single position or wrapped response
        data = positions_data.get("data", positions_data)
        if isinstance(data, list):
            for position in data:
                pos_token = str(position.get("TokenNo", ""))
                if pos_token == str(token):
                    net_qty = str(position.get("Qty", 0))
                    break

    return net_qty


def place_order_api(data, auth):
    """
    Place an order via Evermore OrderEntry API.

    Args:
        data: OpenAlgo order dict
        auth: Auth token in "UniqueId:RefNo" format

    Returns:
        (response, response_data, order_id)
    """
    unique_id, ref_no = parse_auth_token(auth)
    token = get_token(data["symbol"], data["exchange"])
    newdata = transform_data(data, token)

    client = get_httpx_client()
    base_url = get_api_url()
    url = f"{base_url}/api/PublicAPI/OrderEntry"

    # Build Evermore OrderEntry payload
    payload = json.dumps({
        "UniqueId": unique_id,
        "LoginId": os.getenv("EVERMORE_LOGIN_ID", ""),
        "RefNo": ref_no,
        "gateway": newdata["gateway"],
        "Exchange": newdata["Exchange"],
        "Tokenno": newdata["Tokenno"],
        "clientcode": "",  # Default client code
        "Buysell": newdata["Buysell"],
        "qty": newdata["qty"],
        "qtydisclosed": newdata["qtydisclosed"],
        "Price": newdata["Price"],
        "Triggerprice": newdata["Triggerprice"],
        "Booktype": newdata["Booktype"],
        "validity": newdata["validity"],
        "DeliveryType": newdata["DeliveryType"],
    })

    logger.debug(f"Order payload: {payload}")

    response = client.post(url, headers=_get_headers(), content=payload)
    response.status = response.status_code

    response_data = response.json()

    # Evermore returns IntOrdNo on success, Error on failure
    error = response_data.get("Error", "")
    if error:
        logger.error(f"Order placement failed: {error}")
        orderid = None
    else:
        orderid = str(response_data.get("IntOrdNo", ""))
        logger.info(f"Order placed successfully: {orderid}")

    return response, response_data, orderid


def place_smartorder_api(data, auth):
    """
    Place a smart order that adjusts position to target size.

    Smart order logic:
    - If position_size matches current position, do nothing
    - If position needs adjustment, calculate and place appropriate order
    """
    AUTH_TOKEN = auth

    res = None
    symbol = data.get("symbol")
    exchange = data.get("exchange")
    product = data.get("product")
    position_size = int(data.get("position_size", "0"))

    current_position = int(
        get_open_position(symbol, exchange, map_product_type(product), AUTH_TOKEN)
    )

    logger.info(f"position_size : {position_size}")
    logger.info(f"Open Position : {current_position}")

    action = None
    quantity = 0

    if position_size == 0 and current_position == 0 and int(data["quantity"]) != 0:
        action = data["action"]
        quantity = data["quantity"]
        res, response, orderid = place_order_api(data, AUTH_TOKEN)
        return res, response, orderid

    elif position_size == current_position:
        if int(data["quantity"]) == 0:
            response = {
                "status": "success",
                "message": "No OpenPosition Found. Not placing Exit order.",
            }
        else:
            response = {
                "status": "success",
                "message": "No action needed. Position size matches current position",
            }
        orderid = None
        return res, response, orderid

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

    if action:
        order_data = data.copy()
        order_data["action"] = action
        order_data["quantity"] = str(quantity)

        res, response, orderid = place_order_api(order_data, auth)
        logger.info(f"{response}")
        logger.info(f"{orderid}")

        return res, response, orderid


def close_all_positions(current_api_key, auth):
    """Close all open positions by placing counter orders"""
    AUTH_TOKEN = auth

    positions_response = get_positions(AUTH_TOKEN)

    # Handle various response formats
    positions = None
    if isinstance(positions_response, list):
        positions = positions_response
    elif isinstance(positions_response, dict):
        positions = positions_response.get("data")

    if not positions:
        return {"message": "No Open Positions Found"}, 200

    for position in positions:
        qty = int(position.get("Qty", 0))
        if qty == 0:
            continue

        action = "SELL" if qty > 0 else "BUY"
        quantity = abs(qty)

        token_no = str(position.get("TokenNo", ""))
        exchange = position.get("Exchange", "")
        oa_exchange = reverse_map_exchange(exchange)

        symbol = get_symbol(token_no, oa_exchange)
        if not symbol:
            logger.warning(f"Cannot resolve symbol for token {token_no}, skipping")
            continue

        logger.info(f"Closing position: {symbol} qty={quantity} action={action}")

        delivery_type = position.get("DeliveryType", 0)
        product = reverse_map_product_type_with_exchange(delivery_type, exchange)

        place_order_payload = {
            "apikey": current_api_key,
            "strategy": "Squareoff",
            "symbol": symbol,
            "action": action,
            "exchange": oa_exchange,
            "pricetype": "MARKET",
            "product": product,
            "quantity": str(quantity),
        }

        logger.info(f"Squareoff payload: {place_order_payload}")
        res, response, orderid = place_order_api(place_order_payload, auth)

    return {"status": "success", "message": "All Open Positions SquaredOff"}, 200


def cancel_order(orderid, auth):
    """
    Cancel an order via Evermore CancelRequest API.

    Args:
        orderid: Evermore IntOrdNo
        auth: Auth token

    Returns:
        (response_dict, status_code)
    """
    unique_id, ref_no = parse_auth_token(auth)
    client = get_httpx_client()
    base_url = get_api_url()
    url = f"{base_url}/api/PublicAPI/CancelRequest"

    payload = json.dumps({
        "UniqueId": unique_id,
        "RefNo": ref_no,
        "IntOrdNo": str(orderid),
    })

    response = client.post(url, headers=_get_headers(), content=payload)
    response.status = response.status_code

    data = json.loads(response.text)

    error = data.get("Error", "")
    if error:
        return {"status": "error", "message": f"Cancel failed: {error}"}, response.status
    else:
        return {"status": "success", "orderid": str(data.get("IntOrdNo", orderid))}, 200


def modify_order(data, auth):
    """
    Modify an order via Evermore ModifyRequest API.

    Args:
        data: Order modification dict with orderid, quantity, price, etc.
        auth: Auth token

    Returns:
        (response_dict, status_code)
    """
    unique_id, ref_no = parse_auth_token(auth)
    client = get_httpx_client()
    base_url = get_api_url()
    url = f"{base_url}/api/PublicAPI/ModifyRequest"

    token = get_token(data["symbol"], data["exchange"])
    transformed = transform_modify_order_data(data, token)

    payload = json.dumps({
        "UniqueId": unique_id,
        "RefNo": ref_no,
        "IntordNo": transformed["IntordNo"],
        "qty": transformed["qty"],
        "qtydisclosed": transformed["qtydisclosed"],
        "Price": transformed["Price"],
        "TriggerPrice": transformed["TriggerPrice"],
        "Booktype": transformed["Booktype"],
        "Validity": transformed["Validity"],
    })

    response = client.post(url, headers=_get_headers(), content=payload)
    response.status = response.status_code

    resp_data = json.loads(response.text)

    error = resp_data.get("Error", "")
    if error:
        return {"status": "error", "message": f"Modify failed: {error}"}, response.status
    else:
        return {"status": "success", "orderid": str(resp_data.get("IntOrdNo", ""))}, 200


def cancel_all_orders_api(data, auth):
    """
    Cancel all open/pending orders.

    Returns:
        (canceled_orders, failed_cancellations) — two lists of order IDs
    """
    order_book = get_order_book(auth)

    # Extract orders list from response
    orders = None
    if isinstance(order_book, list):
        orders = order_book
    elif isinstance(order_book, dict):
        orders = order_book.get("data", [])

    if not orders:
        return [], []

    # Filter orders that can be cancelled (Submitted or EPEnding)
    orders_to_cancel = [
        order for order in orders
        if order.get("OrderStatus") in ("Submitted", "EPEnding")
    ]

    canceled_orders = []
    failed_cancellations = []

    for order in orders_to_cancel:
        orderid = str(order.get("IntOrdNo", ""))
        cancel_response, status_code = cancel_order(orderid, auth)
        if status_code == 200:
            canceled_orders.append(orderid)
        else:
            failed_cancellations.append(orderid)

    return canceled_orders, failed_cancellations
