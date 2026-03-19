# Mapping OpenAlgo API Request https://openalgo.in/docs
# Mapping Evermore (AutoTradeTech) Order Parameters

from database.token_db import get_br_symbol, get_token


def transform_data(data):
    """
    Transforms OpenAlgo order request to Evermore OrderEntry format.
    """
    symbol = get_br_symbol(data["symbol"], data["exchange"])
    token = get_token(data["symbol"], data["exchange"])

    transformed = {
        "gateway": map_exchange(data["exchange"]),
        "Exchange": map_exchange(data["exchange"]),
        "Tokenno": str(token) if token else "",
        "Buysell": data["action"].upper(),
        "qty": float(data["quantity"]),
        "qtydisclosed": float(data.get("disclosed_quantity", 0)),
        "Price": float(data.get("price", 0)),
        "Triggerprice": float(data.get("trigger_price", 0)),
        "Booktype": map_order_type(data.get("pricetype", "LIMIT")),
        "validity": data.get("validity", "DAY").upper(),
        "DeliveryType": map_product_type(data.get("product", "MIS")),
    }

    return transformed


def transform_modify_order_data(data):
    """
    Transforms OpenAlgo modify order request to Evermore ModifyRequest format.
    """
    return {
        "qty": float(data["quantity"]),
        "qtydisclosed": float(data.get("disclosed_quantity", 0)),
        "Price": float(data.get("price", 0)),
        "TriggerPrice": float(data.get("trigger_price", 0)),
        "Booktype": map_order_type(data.get("pricetype", "LIMIT")),
        "Validity": data.get("validity", "DAY").upper(),
    }


def map_order_type(pricetype):
    """
    Maps OpenAlgo pricetype to Evermore Booktype.

    OpenAlgo: MARKET, LIMIT, SL, SL-M
    Evermore: RL (Regular/Limit), SL (Stop-Loss)
    """
    order_type_mapping = {
        "MARKET": "RL",   # Market orders use RL with Price=0
        "LIMIT": "RL",    # Limit orders use RL with Price>0
        "SL": "SL",       # Stop-Loss Limit
        "SL-M": "SL",     # Stop-Loss Market (Evermore uses SL for both)
    }
    return order_type_mapping.get(pricetype.upper(), "RL")


def map_product_type(product):
    """
    Maps OpenAlgo product to Evermore DeliveryType.

    OpenAlgo: CNC, NRML, MIS
    Evermore: 0=Normal (CNC/NRML), 1=Intraday (MIS)
    """
    product_type_mapping = {
        "CNC": 0,     # Cash and Carry (delivery) → Normal
        "NRML": 0,    # Normal → Normal
        "MIS": 1,     # Margin Intraday → Intraday
    }
    return product_type_mapping.get(product.upper(), 1)


def map_exchange(exchange):
    """
    Maps OpenAlgo exchange to Evermore exchange/gateway.

    OpenAlgo: NSE, NFO, BSE, BFO, CDS, BCD
    Evermore: NSECM, NSEFO, BSE, BSEFO, NSECD, BSECD
    """
    exchange_mapping = {
        "NSE": "NSECM",
        "NFO": "NSEFO",
        "BSE": "BSE",
        "BFO": "BSEFO",
        "CDS": "NSECD",
        "BCD": "BSECD",
    }
    return exchange_mapping.get(exchange.upper(), exchange.upper())


def reverse_map_exchange(evermore_exchange):
    """
    Reverse maps Evermore exchange to OpenAlgo exchange.
    """
    reverse_mapping = {
        "NSECM": "NSE",
        "NSEFO": "NFO",
        "BSE": "BSE",
        "BSEFO": "BFO",
        "NSECD": "CDS",
        "BSECD": "BCD",
    }
    return reverse_mapping.get(evermore_exchange.upper(), evermore_exchange.upper())


def reverse_map_product_type(exchange, delivery_type):
    """
    Reverse maps Evermore DeliveryType to OpenAlgo product type.
    """
    if delivery_type == 1:
        return "MIS"
    # DeliveryType 0 (Normal) → depends on exchange
    if exchange in ("NFO", "NSEFO", "BFO", "BSEFO", "CDS", "NSECD", "BCD", "BSECD"):
        return "NRML"
    return "CNC"
