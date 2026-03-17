# Mapping OpenAlgo API Request https://openalgo.in/docs
# Mapping Evermore REST API Parameters (RESTAPI.pdf)

from database.token_db import get_br_symbol


# Evermore exchange codes: NSECM, NSEFO, BSECM, BSEFO, MCXCM, NSECDS
EXCHANGE_MAP = {
    "NSE": "NSECM",
    "NFO": "NSEFO",
    "BSE": "BSECM",
    "BFO": "BSEFO",
    "MCX": "MCXCM",
    "CDS": "NSECDS",
}

REVERSE_EXCHANGE_MAP = {v: k for k, v in EXCHANGE_MAP.items()}


def map_exchange(exchange):
    """Map OpenAlgo exchange to Evermore exchange code"""
    return EXCHANGE_MAP.get(exchange, exchange)


def reverse_map_exchange(evermore_exchange):
    """Map Evermore exchange code back to OpenAlgo exchange"""
    return REVERSE_EXCHANGE_MAP.get(evermore_exchange, evermore_exchange)


def map_order_type(pricetype):
    """
    Map OpenAlgo pricetype to Evermore Booktype.

    Evermore Booktype: RL (Regular/Limit), SL (Stop Loss)
    """
    order_type_mapping = {
        "MARKET": "RL",
        "LIMIT": "RL",
        "SL": "SL",
        "SL-M": "SL",
    }
    return order_type_mapping.get(pricetype, "RL")


def map_product_type(product):
    """
    Map OpenAlgo product to Evermore DeliveryType.

    Evermore DeliveryType: 0 = NORMAL (CNC/NRML), 1 = Intraday (MIS)
    """
    product_type_mapping = {
        "CNC": 0,
        "NRML": 0,
        "MIS": 1,
    }
    return product_type_mapping.get(product, 1)


def reverse_map_product_type(delivery_type):
    """
    Map Evermore DeliveryType back to OpenAlgo product type.

    Since DeliveryType 0 maps to both CNC and NRML, we default to CNC
    for cash exchanges and NRML for derivatives.
    """
    if delivery_type == 1:
        return "MIS"
    return "CNC"  # Default; caller should refine based on exchange


def reverse_map_product_type_with_exchange(delivery_type, exchange):
    """
    Map Evermore DeliveryType back to OpenAlgo product type, using exchange context.
    """
    if delivery_type == 1:
        return "MIS"
    # DeliveryType 0 = NORMAL
    oa_exchange = reverse_map_exchange(exchange) if exchange in REVERSE_EXCHANGE_MAP else exchange
    if oa_exchange in ("NSE", "BSE"):
        return "CNC"
    return "NRML"


def map_price(pricetype, price):
    """
    Get price value based on order type.
    For MARKET orders, price should be 0.
    """
    if pricetype == "MARKET":
        return "0"
    return str(price)


def map_trigger_price(pricetype, trigger_price):
    """
    Get trigger price — only relevant for SL and SL-M orders.
    """
    if pricetype in ("SL", "SL-M"):
        return str(trigger_price)
    return "0"


def transform_data(data, token):
    """
    Transform OpenAlgo order format to Evermore OrderEntry format.

    Args:
        data: OpenAlgo order dict with keys: symbol, exchange, action, quantity,
              pricetype, product, price, trigger_price, disclosed_quantity
        token: Broker token number from token_db

    Returns:
        Dict with Evermore-specific field names and values
    """
    symbol = get_br_symbol(data["symbol"], data["exchange"])

    return {
        "gateway": map_exchange(data["exchange"]),
        "Exchange": map_exchange(data["exchange"]),
        "Tokenno": str(token),
        "Symbol": symbol,
        "Buysell": data["action"].upper(),  # BUY or SELL
        "qty": str(data["quantity"]),
        "qtydisclosed": str(data.get("disclosed_quantity", "0")),
        "Price": map_price(data["pricetype"], data.get("price", "0")),
        "Triggerprice": map_trigger_price(data["pricetype"], data.get("trigger_price", "0")),
        "Booktype": map_order_type(data["pricetype"]),
        "validity": "DAY",
        "DeliveryType": map_product_type(data["product"]),
    }


def transform_modify_order_data(data, token):
    """
    Transform OpenAlgo modify order format to Evermore ModifyRequest format.

    Args:
        data: OpenAlgo order dict with orderid, symbol, exchange, quantity, etc.
        token: Broker token number

    Returns:
        Dict with Evermore ModifyRequest fields
    """
    return {
        "IntordNo": data["orderid"],
        "qty": str(data["quantity"]),
        "qtydisclosed": str(data.get("disclosed_quantity", "0")),
        "Price": map_price(data["pricetype"], data.get("price", "0")),
        "TriggerPrice": map_trigger_price(data["pricetype"], data.get("trigger_price", "0")),
        "Booktype": map_order_type(data["pricetype"]),
        "Validity": "DAY",
    }
