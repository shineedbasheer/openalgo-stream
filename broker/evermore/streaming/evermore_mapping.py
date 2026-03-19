"""
Evermore WebSocket data mapping utilities.

Maps between Evermore's WebSocket data format and OpenAlgo's standard format.
"""

from datetime import UTC, datetime
from typing import Any, Dict

from utils.logging import get_logger

logger = get_logger(__name__)


class EvermoreExchangeMapper:
    """Maps exchange codes between Evermore and OpenAlgo formats."""

    _OA_TO_EVERMORE = {
        "NSE": "NSECM",
        "NFO": "NSEFO",
        "BSE": "BSE",
        "BFO": "BSEFO",
        "CDS": "NSECD",
        "BCD": "BSECD",
        "NSE_INDEX": "NSECM",
        "BSE_INDEX": "BSE",
    }

    _EVERMORE_TO_OA = {
        "NSECM": "NSE",
        "NSEFO": "NFO",
        "BSE": "BSE",
        "BSEFO": "BFO",
        "NSECD": "CDS",
        "BSECD": "BCD",
    }

    @classmethod
    def to_evermore_exchange(cls, oa_exchange: str) -> str:
        return cls._OA_TO_EVERMORE.get(oa_exchange.upper(), oa_exchange.upper())

    @classmethod
    def to_oa_exchange(cls, evermore_exchange: str) -> str:
        return cls._EVERMORE_TO_OA.get(evermore_exchange.upper(), evermore_exchange.upper())


class EvermoreCapabilityRegistry:
    """Registry for Evermore WebSocket capabilities."""

    # Map OpenAlgo capability flags to Evermore FeedType
    CAPABILITY_MAP = {
        "LTP": 1,       # MarketData
        "QUOTE": 1,     # MarketData
        "DEPTH": 2,     # Depth (5-level)
        "GREEKS": 4,    # Greeks (for options)
    }

    SUPPORTED_CAPABILITIES = set(CAPABILITY_MAP.keys())

    @classmethod
    def get_feed_type(cls, capability: str) -> int:
        return cls.CAPABILITY_MAP.get(capability.upper(), 1)

    @classmethod
    def mode_to_feed_type(cls, mode: int) -> int:
        """
        Map OpenAlgo mode to Evermore FeedType.

        Mode 1 (LTP) → FeedType 1 (MarketData)
        Mode 2 (Quote) → FeedType 1 (MarketData)
        Mode 3 (Full/Depth) → FeedType 2 (Depth)
        """
        mode_map = {
            1: 1,  # LTP → MarketData
            2: 1,  # Quote → MarketData
            3: 2,  # Full → Depth
        }
        return mode_map.get(mode, 1)

    @classmethod
    def is_supported(cls, capability: str) -> bool:
        return capability.upper() in cls.SUPPORTED_CAPABILITIES


class EvermoreDataTransformer:
    """Transforms data between Evermore and OpenAlgo formats."""

    def __init__(self):
        self.logger = get_logger(__name__)

    def transform_market_data(self, data: Dict, symbol: str, exchange: str) -> Dict:
        """
        Transform Evermore MarketData to OpenAlgo tick format.

        Args:
            data: Raw MarketData from Evermore WebSocket
            symbol: Trading symbol
            exchange: OpenAlgo exchange code

        Returns:
            Transformed tick data in OpenAlgo format
        """
        try:
            if not data:
                return {}

            transformed = {
                "symbol": symbol,
                "exchange": exchange,
                "token": str(data.get("Tkn", "")),
                "last_price": float(data.get("LTP", 0)),
                "volume": int(float(data.get("TTQ", 0))),
                "total_buy_quantity": int(float(data.get("TBQ", 0))),
                "total_sell_quantity": int(float(data.get("TSQ", 0))),
                "average_price": float(data.get("ATP", 0)),
                "mode": "quote",
                "timestamp": int(datetime.now(UTC).timestamp() * 1000),
                "open": float(data.get("O", 0)),
                "high": float(data.get("H", 0)),
                "low": float(data.get("L", 0)),
                "close": float(data.get("C", 0)),
                "oi": int(float(data.get("OI", 0))),
            }

            return transformed

        except Exception as e:
            self.logger.error(f"Error transforming MarketData: {e}")
            return {}

    def transform_depth(self, data: Dict, symbol: str, exchange: str) -> Dict:
        """
        Transform Evermore Depth to OpenAlgo format.

        Args:
            data: Raw Depth data from Evermore WebSocket
            symbol: Trading symbol
            exchange: OpenAlgo exchange code

        Returns:
            Transformed depth data
        """
        try:
            if not data:
                return {}

            depths = data.get("Depths", [])
            buy_depth = []
            sell_depth = []

            for i, level in enumerate(depths):
                buy_depth.append({
                    "price": float(level.get("BP", 0)),
                    "quantity": int(float(level.get("BQ", 0))),
                    "orders": int(float(level.get("BO", 0))),
                    "position": i + 1,
                })
                sell_depth.append({
                    "price": float(level.get("SP", 0)),
                    "quantity": int(float(level.get("SQ", 0))),
                    "orders": int(float(level.get("SO", 0))),
                    "position": i + 1,
                })

            transformed = {
                "symbol": symbol,
                "exchange": exchange,
                "token": str(data.get("Tkn", "")),
                "last_price": float(data.get("LTP", 0)) if "LTP" in data else 0,
                "mode": "full",
                "timestamp": int(datetime.now(UTC).timestamp() * 1000),
                "depth": {
                    "buy": buy_depth,
                    "sell": sell_depth,
                },
            }

            return transformed

        except Exception as e:
            self.logger.error(f"Error transforming Depth data: {e}")
            return {}

    def transform_greek(self, data: Dict, symbol: str, exchange: str) -> Dict:
        """Transform Evermore Greek data to OpenAlgo format."""
        try:
            if not data:
                return {}

            # Greeks include all MarketData fields plus options greeks
            transformed = self.transform_market_data(data, symbol, exchange)
            transformed.update({
                "iv": float(data.get("IV", 0)),
                "delta": float(data.get("Delta", 0)),
                "gamma": float(data.get("Gamma", 0)),
                "theta": float(data.get("Theta", 0)),
                "vega": float(data.get("Vega", 0)),
                "rho": float(data.get("Rho", 0)),
                "spot_price": float(data.get("SpotPrice", 0)),
            })

            return transformed

        except Exception as e:
            self.logger.error(f"Error transforming Greek data: {e}")
            return {}


# Singleton instances
exchange_mapper = EvermoreExchangeMapper()
capability_registry = EvermoreCapabilityRegistry()
data_transformer = EvermoreDataTransformer()
