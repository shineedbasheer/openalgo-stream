# mapping/margin_data.py
# Evermore (AutoTradeTech) does not provide a margin calculation API.
# This is a stub implementation.

from utils.logging import get_logger

logger = get_logger(__name__)


def transform_margin_positions(positions):
    """Stub: Evermore has no margin API."""
    return []


def map_product_type(product):
    """Maps product type for margin calculation."""
    product_mapping = {
        "CNC": "CNC",
        "NRML": "NRML",
        "MIS": "MIS",
    }
    return product_mapping.get(product, "MIS")


def map_order_type(pricetype):
    """Maps order type for margin calculation."""
    order_type_mapping = {
        "MARKET": "RL",
        "LIMIT": "RL",
        "SL": "SL",
        "SL-M": "SL",
    }
    return order_type_mapping.get(pricetype, "RL")


def parse_margin_response(response_data):
    """Stub: Evermore has no margin response to parse."""
    return {
        "required_margin": 0.0,
        "available_margin": 0.0,
        "margin_benefit": 0.0,
    }
