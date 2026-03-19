# api/funds.py
# Evermore (AutoTradeTech) does not provide a funds/margin API.
# This is a stub implementation returning empty values.

from utils.logging import get_logger

logger = get_logger(__name__)


def get_margin_data(auth_token):
    """
    Fetch margin data from Evermore's API.

    Note: Evermore does not provide a funds/margin API endpoint.
    Returns default zero values.
    """
    logger.info("Evermore: Funds API not available - returning default values")
    return {
        "availablecash": "0.00",
        "collateral": "0.00",
        "m2munrealized": "0.00",
        "m2mrealized": "0.00",
        "utiliseddebits": "0.00",
    }
