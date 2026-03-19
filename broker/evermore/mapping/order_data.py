# Mapping Evermore (AutoTradeTech) Response Data to OpenAlgo Format

import json

from broker.evermore.mapping.transform_data import reverse_map_exchange, reverse_map_product_type
from database.token_db import get_oa_symbol, get_symbol
from utils.logging import get_logger

logger = get_logger(__name__)

# Evermore order status → OpenAlgo status (case-insensitive)
STATUS_MAP = {
    "submitted": "open",
    "epending": "open",
    "executed": "complete",
    "erejected": "rejected",
    "mrejected": "rejected",
    "ecancelled": "cancelled",
}


def _normalize_status(evermore_status):
    """Normalize Evermore order status to OpenAlgo format."""
    if not evermore_status:
        return "unknown"
    return STATUS_MAP.get(evermore_status.lower(), evermore_status.lower())


def map_order_data(order_data):
    """
    Processes and modifies a list of order dictionaries from Evermore.
    Converts broker symbols to OpenAlgo symbols.

    Evermore returns order data directly as a list (no 'data' wrapper).
    """
    if order_data is None:
        logger.info("No order data available.")
        return []

    # Evermore returns a direct list, not wrapped in {"data": [...]}
    if isinstance(order_data, dict) and "data" in order_data:
        order_data = order_data["data"]

    if not order_data:
        return []

    for order in order_data:
        token_no = str(order.get("TokenNo", ""))
        exchange = reverse_map_exchange(order.get("Exchange", order.get("gateway", "")))

        if token_no:
            # Look up OA symbol from token
            oa_symbol = get_symbol(token_no, exchange)
            if oa_symbol:
                order["tradingsymbol"] = oa_symbol
            else:
                order["tradingsymbol"] = token_no
        order["exchange"] = exchange

    return order_data


def calculate_order_statistics(order_data):
    """
    Calculates statistics from order data.
    """
    total_buy_orders = total_sell_orders = 0
    total_completed_orders = total_open_orders = total_rejected_orders = 0

    if order_data:
        for order in order_data:
            # Count buy and sell orders
            buy_sell = order.get("BuySell", order.get("Buysell", "")).upper()
            if buy_sell == "BUY":
                total_buy_orders += 1
            elif buy_sell == "SELL":
                total_sell_orders += 1

            # Count orders based on their status
            status = _normalize_status(order.get("OrderStatus", ""))
            if status == "complete":
                total_completed_orders += 1
            elif status == "open":
                total_open_orders += 1
            elif status == "rejected":
                total_rejected_orders += 1

    return {
        "total_buy_orders": total_buy_orders,
        "total_sell_orders": total_sell_orders,
        "total_completed_orders": total_completed_orders,
        "total_open_orders": total_open_orders,
        "total_rejected_orders": total_rejected_orders,
    }


def transform_order_data(orders):
    """
    Transform Evermore order data to OpenAlgo standard format.
    """
    if isinstance(orders, dict):
        orders = [orders]

    transformed_orders = []

    for order in orders:
        if not isinstance(order, dict):
            logger.warning(f"Expected a dict, but found a {type(order)}. Skipping.")
            continue

        order_status = _normalize_status(order.get("OrderStatus", ""))

        transformed_order = {
            "symbol": order.get("tradingsymbol", str(order.get("TokenNo", ""))),
            "exchange": order.get("exchange", reverse_map_exchange(order.get("Exchange", ""))),
            "action": order.get("BuySell", order.get("Buysell", "")).upper(),
            "quantity": int(float(order.get("QtyRemaining", 0)) + float(order.get("QtyTraded", 0))),
            "price": float(order.get("OrderPrice", 0)),
            "trigger_price": float(order.get("TriggerPrice", 0)),
            "pricetype": "SL" if float(order.get("TriggerPrice", 0)) > 0 else "LIMIT",
            "product": reverse_map_product_type(
                order.get("exchange", ""),
                order.get("DeliveryType", 0)
            ),
            "orderid": str(order.get("IntOrdNo", "")),
            "order_status": order_status,
            "timestamp": str(order.get("OrderTime", "")),
        }

        transformed_orders.append(transformed_order)

    return transformed_orders


def map_trade_data(trade_data):
    """Map trade data - same logic as order data mapping."""
    return map_order_data(trade_data)


def transform_tradebook_data(tradebook_data):
    """Transform Evermore trade data to OpenAlgo format."""
    transformed_data = []

    if not tradebook_data:
        return transformed_data

    for trade in tradebook_data:
        transformed_trade = {
            "symbol": trade.get("tradingsymbol", str(trade.get("TokenNo", ""))),
            "exchange": trade.get("exchange", reverse_map_exchange(trade.get("Exchange", ""))),
            "product": reverse_map_product_type(
                trade.get("exchange", ""),
                trade.get("DeliveryType", 0)
            ),
            "action": trade.get("BuySell", trade.get("Buysell", "")).upper(),
            "quantity": int(float(trade.get("QtyTraded", 0))),
            "average_price": float(trade.get("TradePrice", 0)),
            "trade_value": float(trade.get("QtyTraded", 0)) * float(trade.get("TradePrice", 0)),
            "orderid": str(trade.get("IntOrdNo", "")),
            "timestamp": str(trade.get("TradeTime", "")),
        }
        transformed_data.append(transformed_trade)

    return transformed_data


def map_position_data(position_data):
    """
    Processes and modifies a list of position dictionaries from Evermore.
    """
    if position_data is None:
        logger.info("No position data available.")
        return []

    # Evermore returns a direct list
    if isinstance(position_data, dict):
        if "data" in position_data:
            position_data = position_data["data"]
            if isinstance(position_data, dict) and "net" in position_data:
                position_data = position_data["net"]

    if not position_data:
        return []

    for position in position_data:
        token_no = str(position.get("TokenNo", ""))
        exchange = reverse_map_exchange(position.get("Exchange", ""))

        if token_no:
            oa_symbol = get_symbol(token_no, exchange)
            if oa_symbol:
                position["tradingsymbol"] = oa_symbol
            else:
                position["tradingsymbol"] = token_no
        position["exchange"] = exchange

    return position_data


def transform_positions_data(positions_data):
    """Transform Evermore position data to OpenAlgo format."""
    transformed_data = []

    if not positions_data:
        return transformed_data

    for position in positions_data:
        average_price = float(position.get("Average", 0))
        average_price_formatted = "{:.2f}".format(average_price)

        transformed_position = {
            "symbol": position.get("tradingsymbol", str(position.get("TokenNo", ""))),
            "exchange": position.get("exchange", reverse_map_exchange(position.get("Exchange", ""))),
            "product": reverse_map_product_type(
                position.get("exchange", ""),
                position.get("DeliveryType", 0)
            ),
            "quantity": str(int(float(position.get("Qty", 0)))),
            "pnl": 0.0,  # Evermore doesn't provide PnL in positions
            "average_price": average_price_formatted,
            "ltp": 0.0,  # Evermore doesn't provide LTP in position response
        }
        transformed_data.append(transformed_position)

    return transformed_data


def transform_holdings_data(holdings_data):
    """
    Evermore does not provide a holdings API.
    Returns empty list.
    """
    return []


def map_portfolio_data(portfolio_data):
    """
    Evermore does not provide a portfolio/holdings API.
    Returns empty list.
    """
    return []


def calculate_portfolio_statistics(holdings_data):
    """
    Calculate portfolio statistics.
    Returns zeros since Evermore has no holdings API.
    """
    return {
        "totalholdingvalue": 0,
        "totalinvvalue": 0,
        "totalprofitandloss": 0,
        "totalpnlpercentage": 0,
    }
