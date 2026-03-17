from database.token_db import get_symbol
from broker.evermore.mapping.transform_data import (
    reverse_map_exchange,
    reverse_map_product_type_with_exchange,
)
from utils.logging import get_logger

logger = get_logger(__name__)


# Evermore order status → OpenAlgo status mapping
ORDER_STATUS_MAP = {
    "Submitted": "open",
    "EPEnding": "pending",
    "Ecancelled": "cancelled",
    "ERejected": "rejected",
    "MRejected": "rejected",
    "Executed": "complete",
}


def map_order_status(evermore_status):
    """Map Evermore order status to OpenAlgo standard status"""
    return ORDER_STATUS_MAP.get(evermore_status, evermore_status.lower())


def map_order_data(order_data):
    """
    Process Evermore OrderBookRequest response into OpenAlgo format.

    Evermore returns a collection with fields:
    IntOrdNo, TokenNo, ExchOrdNo, QtyRemaining, QtyTraded,
    OrderStatus, OrderPrice, OrderTime, BuySell, TriggerPrice, Exchange, etc.

    Returns:
        List of order dicts with OpenAlgo field names
    """
    if not order_data:
        logger.info("No order data available.")
        return []

    orders = order_data if isinstance(order_data, list) else [order_data]

    for order in orders:
        token_no = str(order.get("TokenNo", ""))
        exchange = order.get("Exchange", "")
        oa_exchange = reverse_map_exchange(exchange)

        # Reverse lookup symbol from token
        symbol_from_db = get_symbol(token_no, oa_exchange)
        if symbol_from_db:
            order["tradingsymbol"] = symbol_from_db
        else:
            order["tradingsymbol"] = order.get("Symbol", "")
            logger.info(
                f"Symbol not found for token {token_no} and exchange {oa_exchange}. "
                f"Keeping original symbol."
            )

        order["exchange"] = oa_exchange

        # Map product type using exchange context
        delivery_type = order.get("DeliveryType", 0)
        order["producttype"] = reverse_map_product_type_with_exchange(delivery_type, exchange)

        # Map order status
        order["status"] = map_order_status(order.get("OrderStatus", ""))

    return orders


def calculate_order_statistics(order_data):
    """
    Calculate order statistics from mapped order data.

    Returns:
        Dict with counts of buy, sell, completed, open, rejected orders
    """
    total_buy_orders = total_sell_orders = 0
    total_completed_orders = total_open_orders = total_rejected_orders = 0

    if order_data:
        for order in order_data:
            action = order.get("BuySell", "").upper()
            if action == "BUY":
                total_buy_orders += 1
            elif action == "SELL":
                total_sell_orders += 1

            status = order.get("status", "")
            if status == "complete":
                total_completed_orders += 1
            elif status in ("open", "pending"):
                total_open_orders += 1
            elif status in ("rejected", "cancelled"):
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
    Transform Evermore order book data to OpenAlgo standardized format.

    Maps Evermore fields → OpenAlgo fields:
    - IntOrdNo → orderid
    - BuySell → action
    - OrderPrice → price
    - TriggerPrice → trigger_price
    - OrderStatus → order_status (mapped)
    - OrderTime → timestamp
    """
    if isinstance(orders, dict):
        orders = [orders]

    transformed_orders = []

    for order in orders:
        if not isinstance(order, dict):
            logger.warning(f"Expected dict, found {type(order)}. Skipping.")
            continue

        # Map Evermore Booktype → OpenAlgo pricetype
        booktype = order.get("Booktype", "RL")
        trigger_price = float(order.get("TriggerPrice", 0))

        if booktype == "SL" and trigger_price > 0:
            price = float(order.get("OrderPrice", 0))
            pricetype = "SL" if price > 0 else "SL-M"
        else:
            price = float(order.get("OrderPrice", 0))
            pricetype = "LIMIT" if price > 0 else "MARKET"

        transformed_order = {
            "symbol": order.get("tradingsymbol", ""),
            "exchange": order.get("exchange", ""),
            "action": order.get("BuySell", "").upper(),
            "quantity": order.get("QtyRemaining", 0) + order.get("QtyTraded", 0),
            "price": order.get("OrderPrice", 0.0),
            "trigger_price": trigger_price,
            "pricetype": pricetype,
            "product": order.get("producttype", ""),
            "orderid": str(order.get("IntOrdNo", "")),
            "order_status": order.get("status", ""),
            "timestamp": order.get("OrderTime", ""),
        }

        transformed_orders.append(transformed_order)

    return transformed_orders


def map_trade_data(trade_data):
    """
    Process Evermore TradeBookRequest response.

    Evermore trade fields:
    IntOrdNo, TokenNo, QtyTraded, TradePrice, TradeTime, ExchOrdNo, TradeNo, BuySell
    """
    if not trade_data:
        logger.info("No trade data available.")
        return []

    trades = trade_data if isinstance(trade_data, list) else [trade_data]

    for trade in trades:
        token_no = str(trade.get("TokenNo", ""))
        exchange = trade.get("Exchange", "")
        oa_exchange = reverse_map_exchange(exchange)

        symbol_from_db = get_symbol(token_no, oa_exchange)
        if symbol_from_db:
            trade["tradingsymbol"] = symbol_from_db
        else:
            trade["tradingsymbol"] = trade.get("Symbol", "")

        trade["exchange"] = oa_exchange

        delivery_type = trade.get("DeliveryType", 0)
        trade["producttype"] = reverse_map_product_type_with_exchange(delivery_type, exchange)

    return trades


def transform_tradebook_data(tradebook_data):
    """Transform Evermore trade data to OpenAlgo standardized format."""
    transformed_data = []
    for trade in tradebook_data:
        transformed_trade = {
            "symbol": trade.get("tradingsymbol", ""),
            "exchange": trade.get("exchange", ""),
            "product": trade.get("producttype", ""),
            "action": trade.get("BuySell", "").upper(),
            "quantity": trade.get("QtyTraded", 0),
            "average_price": trade.get("TradePrice", 0.0),
            "trade_value": float(trade.get("QtyTraded", 0)) * float(trade.get("TradePrice", 0)),
            "orderid": str(trade.get("IntOrdNo", "")),
            "timestamp": trade.get("TradeTime", ""),
        }
        transformed_data.append(transformed_trade)
    return transformed_data


def map_position_data(position_data):
    """
    Process Evermore PositionRequest response.

    Evermore position fields: TokenNo, ClientCode, Qty, Average
    """
    if not position_data:
        logger.info("No position data available.")
        return []

    positions = position_data if isinstance(position_data, list) else [position_data]

    for position in positions:
        token_no = str(position.get("TokenNo", ""))
        exchange = position.get("Exchange", "")
        oa_exchange = reverse_map_exchange(exchange)

        symbol_from_db = get_symbol(token_no, oa_exchange)
        if symbol_from_db:
            position["tradingsymbol"] = symbol_from_db
        else:
            position["tradingsymbol"] = position.get("Symbol", "")

        position["exchange"] = oa_exchange

        delivery_type = position.get("DeliveryType", 0)
        position["producttype"] = reverse_map_product_type_with_exchange(delivery_type, exchange)

    return positions


def transform_positions_data(positions_data):
    """Transform Evermore position data to OpenAlgo standardized format."""
    transformed_data = []
    for position in positions_data:
        qty = int(position.get("Qty", 0))
        avg_price = float(position.get("Average", 0))

        transformed_position = {
            "symbol": position.get("tradingsymbol", ""),
            "exchange": position.get("exchange", ""),
            "product": position.get("producttype", ""),
            "quantity": qty,
            "average_price": avg_price,
            "ltp": position.get("ltp", 0.0),
            "pnl": position.get("pnl", 0.0),
        }
        transformed_data.append(transformed_position)
    return transformed_data
