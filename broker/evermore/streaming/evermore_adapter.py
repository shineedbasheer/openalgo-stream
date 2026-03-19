"""
Evermore WebSocket Adapter

Implements the OpenAlgo BaseBrokerWebSocketAdapter interface for Evermore.
Handles subscription management, data transformation, and ZMQ publishing.
"""

import json
import os
import threading
import time
from typing import Any, Dict, List, Optional, Set

from database.auth_db import get_auth_token
from database.token_db import get_token
from websocket_proxy.base_adapter import BaseBrokerWebSocketAdapter

from .evermore_mapping import (
    EvermoreCapabilityRegistry,
    EvermoreDataTransformer,
    EvermoreExchangeMapper,
)
from .evermore_websocket import EvermoreWebSocket

from utils.logging import get_logger

logger = get_logger(__name__)


class EvermoreWebSocketAdapter(BaseBrokerWebSocketAdapter):
    """
    Evermore-specific implementation of the WebSocket adapter.
    Implements OpenAlgo WebSocket proxy interface for real-time market data.
    """

    def __init__(self):
        super().__init__()
        self.logger = get_logger("evermore_websocket")
        self.ws_client: Optional[EvermoreWebSocket] = None
        self.user_id = None
        self.broker_name = "evermore"
        self.running = False
        self.connected = False
        self.lock = threading.Lock()

        # Symbol tracking
        self.subscribed_symbols: Dict[str, Dict] = {}  # {symbol: {exchange, token, mode}}
        self.token_to_symbol: Dict[str, tuple] = {}  # {token: (symbol, exchange)}

        # Data transformer
        self.transformer = EvermoreDataTransformer()

        # Connection management
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 5

        # Mode mapping: OpenAlgo mode → Evermore FeedType
        self.mode_map = {
            1: 1,  # LTP → MarketData
            2: 1,  # Quote → MarketData
            3: 2,  # Full/Depth → Depth
        }

        # Batch subscription management
        self.subscription_queue: List = []
        self.batch_timer = None
        self.batch_delay = 0.5  # 500ms delay to collect batch

    def initialize(
        self, broker_name: str, user_id: str, auth_data: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Initialize the adapter with broker credentials."""
        try:
            if broker_name != self.broker_name:
                return {"status": "error", "message": f"Invalid broker name: {broker_name}"}

            self.user_id = user_id

            # Get credentials from environment
            login_id = os.getenv("BROKER_API_KEY")
            password = os.getenv("BROKER_API_SECRET")
            ws_url = os.getenv("EVERMORE_WS_URL", "ws://192.168.6.164:19101")

            if not login_id or not password:
                return {
                    "status": "error",
                    "message": "BROKER_API_KEY and BROKER_API_SECRET must be set for Evermore",
                }

            # Create WebSocket client
            self.ws_client = EvermoreWebSocket(
                login_id=login_id,
                password=password,
                url=ws_url,
            )

            # Set up tick handler
            self.ws_client.on_tick = self._handle_ticks
            self.ws_client.on_disconnect = self._handle_disconnect

            self.logger.info(f"Evermore adapter initialized for user {user_id}")
            return {
                "status": "success",
                "message": f"Evermore adapter initialized",
                "zmq_port": self.zmq_port,
            }

        except Exception as e:
            self.logger.exception(f"Error initializing Evermore adapter: {e}")
            return {"status": "error", "message": str(e)}

    def connect(self) -> Dict[str, Any]:
        """Establish connection to Evermore WebSocket."""
        try:
            if not self.ws_client:
                return {"status": "error", "message": "Adapter not initialized"}

            self.running = True
            success = self.ws_client.connect(timeout=15.0)

            if success:
                self.connected = True
                self.reconnect_attempts = 0
                self.logger.info("Evermore WebSocket connected and authenticated")
                return {"status": "success", "message": "Connected to Evermore"}
            else:
                self.logger.error("Evermore WebSocket connection/login failed")
                return {"status": "error", "message": "Failed to connect to Evermore WebSocket"}

        except Exception as e:
            self.logger.exception(f"Error connecting to Evermore: {e}")
            return {"status": "error", "message": str(e)}

    def disconnect(self) -> Dict[str, Any]:
        """Disconnect from Evermore WebSocket."""
        try:
            self.running = False
            self.connected = False

            if self.ws_client:
                self.ws_client.disconnect()

            # Cleanup ZMQ
            self.cleanup_zmq()

            self.subscribed_symbols.clear()
            self.token_to_symbol.clear()

            self.logger.info("Evermore WebSocket disconnected")
            return {"status": "success", "message": "Disconnected from Evermore"}

        except Exception as e:
            self.logger.exception(f"Error disconnecting: {e}")
            return {"status": "error", "message": str(e)}

    def subscribe(
        self, symbol: str, exchange: str, mode: int = 2, depth_level: int = 5
    ) -> Dict[str, Any]:
        """
        Subscribe to market data for a symbol.

        Args:
            symbol: Trading symbol (e.g., 'RELIANCE')
            exchange: Exchange code (e.g., 'NSE')
            mode: 1=LTP, 2=Quote, 3=Depth
            depth_level: Market depth level (ignored — Evermore always gives 5 levels)
        """
        try:
            if not self.connected:
                return {"status": "error", "message": "Not connected"}

            # Get token from database
            token = get_token(symbol, exchange)
            if not token:
                return {"status": "error", "message": f"Token not found for {symbol}:{exchange}"}

            # Map to Evermore exchange
            evermore_exchange = EvermoreExchangeMapper.to_evermore_exchange(exchange)
            feed_type = self.mode_map.get(mode, 1)

            # Track subscription
            sub_key = f"{symbol}:{exchange}"
            self.subscribed_symbols[sub_key] = {
                "exchange": exchange,
                "token": str(token),
                "mode": mode,
                "feed_type": feed_type,
            }
            self.token_to_symbol[str(token)] = (symbol, exchange)

            # Subscribe via WebSocket
            quotes = [{
                "Xchg": evermore_exchange,
                "Tkn": str(token),
                "Symbol": symbol,
            }]
            self.ws_client.subscribe(quotes, feed_type=feed_type)

            self.logger.info(
                f"Subscribed to {symbol}:{exchange} (Token={token}, FeedType={feed_type})"
            )
            return {
                "status": "success",
                "message": f"Subscribed to {symbol}",
                "capability": "QUOTE" if feed_type == 1 else "DEPTH",
            }

        except Exception as e:
            self.logger.exception(f"Error subscribing to {symbol}:{exchange}: {e}")
            return {"status": "error", "message": str(e)}

    def unsubscribe(self, symbol: str, exchange: str, mode: int = 2) -> Dict[str, Any]:
        """Unsubscribe from market data."""
        try:
            if not self.connected:
                return {"status": "error", "message": "Not connected"}

            sub_key = f"{symbol}:{exchange}"
            sub_info = self.subscribed_symbols.pop(sub_key, None)

            if not sub_info:
                return {"status": "success", "message": f"Not subscribed to {symbol}"}

            token = sub_info["token"]
            feed_type = sub_info.get("feed_type", 1)
            evermore_exchange = EvermoreExchangeMapper.to_evermore_exchange(exchange)

            # Remove token mapping
            self.token_to_symbol.pop(str(token), None)

            # Unsubscribe via WebSocket
            quotes = [{
                "Xchg": evermore_exchange,
                "Tkn": str(token),
                "Symbol": symbol,
            }]
            self.ws_client.unsubscribe(quotes, feed_type=feed_type)

            self.logger.info(f"Unsubscribed from {symbol}:{exchange}")
            return {"status": "success", "message": f"Unsubscribed from {symbol}"}

        except Exception as e:
            self.logger.exception(f"Error unsubscribing from {symbol}:{exchange}: {e}")
            return {"status": "error", "message": str(e)}

    def unsubscribe_all(self):
        """Unsubscribe from all symbols."""
        for sub_key in list(self.subscribed_symbols.keys()):
            symbol, exchange = sub_key.split(":", 1)
            self.unsubscribe(symbol, exchange)
        self.logger.info("Unsubscribed from all symbols")

    def _handle_ticks(self, msg_type: str, data: Any):
        """
        Handle incoming WebSocket tick data.
        Transform and publish via ZMQ.
        """
        try:
            if not data:
                return

            # IndexData comes as array
            if msg_type == "IndexData" and isinstance(data, list):
                for index_data in data:
                    topic = f"INDEX_{index_data.get('Symbol', 'UNKNOWN')}"
                    self.publish_market_data(topic, json.dumps(index_data))
                return

            # MarketData, Depth, Greek come as single objects
            token = str(data.get("Tkn", ""))

            if token in self.token_to_symbol:
                symbol, exchange = self.token_to_symbol[token]

                if msg_type == "MarketData":
                    transformed = self.transformer.transform_market_data(data, symbol, exchange)
                elif msg_type == "Depth":
                    transformed = self.transformer.transform_depth(data, symbol, exchange)
                elif msg_type == "Greek":
                    transformed = self.transformer.transform_greek(data, symbol, exchange)
                else:
                    transformed = data

                if transformed:
                    # Generate topic matching OpenAlgo format
                    topic = f"{exchange}_{symbol}"
                    self.publish_market_data(topic, json.dumps(transformed))

        except Exception as e:
            self.logger.error(f"Error handling tick: {e}")

    def _handle_disconnect(self):
        """Handle unexpected disconnection."""
        self.connected = False
        self.logger.warning("Evermore WebSocket disconnected unexpectedly")

        if self.running and self.reconnect_attempts < self.max_reconnect_attempts:
            self.reconnect_attempts += 1
            self.logger.info(
                f"Attempting reconnect ({self.reconnect_attempts}/{self.max_reconnect_attempts}) "
                f"in {self.reconnect_delay}s..."
            )
            time.sleep(self.reconnect_delay)

            # Reconnect
            result = self.connect()
            if result.get("status") == "success":
                # Resubscribe all
                for sub_key, sub_info in list(self.subscribed_symbols.items()):
                    symbol, exchange = sub_key.split(":", 1)
                    self.subscribe(symbol, exchange, mode=sub_info["mode"])
                self.logger.info("Reconnection successful — resubscribed all symbols")
            else:
                self.logger.error(f"Reconnection failed: {result}")
