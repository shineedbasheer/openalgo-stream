"""
Evermore WebSocket data mapping utilities.

Maps between Evermore's MT Data Feed API format and OpenAlgo's standard format.
Evermore uses exchange codes like NSECM, NSEFO, BSECM, MCXCM etc.
"""

from utils.logging import get_logger

logger = get_logger(__name__)


class EvermoreExchangeMapper:
    """Maps exchange codes between Evermore and OpenAlgo formats"""

    # Map OpenAlgo exchange codes to Evermore exchange codes
    _OA_TO_EVERMORE = {
        "NSE": "NSECM",
        "NFO": "NSEFO",
        "BSE": "BSECM",
        "BFO": "BSEFO",
        "MCX": "MCXCM",
        "CDS": "NSECDS",
        "NSE_INDEX": "NSECM",
        "BSE_INDEX": "BSECM",
    }

    # Map Evermore exchange codes to OpenAlgo exchange codes
    _EVERMORE_TO_OA = {
        "NSECM": "NSE",
        "NSEFO": "NFO",
        "BSECM": "BSE",
        "BSEFO": "BFO",
        "MCXCM": "MCX",
        "NSECDS": "CDS",
    }

    @classmethod
    def to_evermore_exchange(cls, oa_exchange: str) -> str:
        return cls._OA_TO_EVERMORE.get(oa_exchange.upper(), oa_exchange.upper())

    @classmethod
    def to_oa_exchange(cls, evermore_exchange: str) -> str:
        return cls._EVERMORE_TO_OA.get(evermore_exchange.upper(), evermore_exchange.upper())


class EvermoreCapabilityRegistry:
    """Registry for Evermore WebSocket capabilities"""

    # Evermore FeedType: 1=MarketData, 2=Depth, 3=SnapQuote, 4=Greeks
    CAPABILITY_MAP = {
        "LTP": 1,      # MarketData (contains LTP + OHLCV)
        "QUOTE": 1,    # MarketData (same feed, OpenAlgo extracts quote fields)
        "DEPTH": 2,    # Depth (5-level bid/ask)
    }

    SUPPORTED_CAPABILITIES = {"LTP", "QUOTE", "DEPTH"}

    # Supported exchanges
    exchanges = ["NSE", "BSE", "NFO", "BFO", "MCX", "CDS"]
    subscription_modes = [1, 2, 3]  # 1: LTP, 2: Quote, 3: Depth

    # Depth support per exchange
    depth_support = {
        "NSE": [5],
        "BSE": [5],
        "NFO": [5],
        "BFO": [5],
        "MCX": [5],
        "CDS": [5],
    }

    @classmethod
    def get_evermore_feed_type(cls, capability: str) -> int:
        return cls.CAPABILITY_MAP.get(capability.upper(), 1)

    @classmethod
    def is_supported(cls, capability: str) -> bool:
        return capability.upper() in cls.SUPPORTED_CAPABILITIES

    @classmethod
    def get_supported_depth_levels(cls, exchange: str) -> list:
        return cls.depth_support.get(exchange, [5])

    @classmethod
    def is_depth_level_supported(cls, exchange: str, depth_level: int) -> bool:
        return depth_level in cls.get_supported_depth_levels(exchange)

    @classmethod
    def get_fallback_depth_level(cls, exchange: str, requested_depth: int) -> int:
        supported = cls.get_supported_depth_levels(exchange)
        fallbacks = [d for d in supported if d <= requested_depth]
        return max(fallbacks) if fallbacks else 5


# Singleton instances
exchange_mapper = EvermoreExchangeMapper()
capability_registry = EvermoreCapabilityRegistry()
