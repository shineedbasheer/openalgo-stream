"""
Evermore WebSocket adapter for OpenAlgo.

Implements BaseBrokerWebSocketAdapter for the Evermore MT Data Feed API.
Handles MarketData, Depth, and IndexData feeds, transforming them to
OpenAlgo's standard format and publishing via ZeroMQ.

Protocol: JSON over WebSocket
Endpoints: wss://feedapi.com (live), ws://115.242.15.134:19101 (UAT)
"""

import os
import threading
import time
from typing import Any, Dict, Optional

from database.auth_db import get_auth_token
from database.token_db import get_token
from websocket_proxy.base_adapter import BaseBrokerWebSocketAdapter

from .evermore_mapping import EvermoreExchangeMapper
from .evermore_websocket import EvermoreWebSocket

from utils.logging import get_logger

logger = get_logger(__name__)


class EvermoreWebSocketAdapter(BaseBrokerWebSocketAdapter):
    """
    Evermore-specific implementation of the WebSocket adapter.
    Bridges the Evermore MT Data Feed API to OpenAlgo's unified streaming interface.
    """

    def __init__(self):
        super().__init__()
        self.logger = get_logger("evermore_websocket")
        self.ws_client: Optional[EvermoreWebSocket] = None
        self.user_id: Optional[str] = None
        self.broker_name = "evermore"
        self.running = False
        self.connected = False
        self.lock = threading.Lock()

        # Symbol tracking: {"{exchange}:{symbol}": {exchange, symbol, token, mode, ...}}
        self.subscribed_symbols: Dict[str, Dict] = {}
        # Reverse lookup: {"{evermore_xchg}:{evermore_token}": (symbol, oa_exchange)}
        self.token_to_symbol: Dict[str, tuple] = {}

        # Authentication
        self.login_id: Optional[str] = None
        self.password: Optional[str] = None

        # Reconnection
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5

        # Batch subscription management
        self.subscription_queue: list = []
        self.batch_timer: Optional[threading.Timer] = None
        self.batch_delay = 0.5  # 500ms to collect batch

    def initialize(
        self, broker_name: str, user_id: str, auth_data: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Initialize the adapter with Evermore credentials"""
        try:
            if broker_name != self.broker_name:
                return {"status": "error", "message": f"Invalid broker name: {broker_name}"}

            self.user_id = user_id

            # Get credentials from auth_data or environment/database
            if auth_data:
                self.login_id = auth_data.get("login_id")
                self.password = auth_data.get("password")
            else:
                # Try environment variables first
                self.login_id = os.getenv("EVERMORE_LOGIN_ID")
                self.password = os.getenv("EVERMORE_PASSWORD")

                # Fall back to database auth token (format: login_id:password)
                if not self.login_id or not self.password:
                    auth_token = get_auth_token(user_id)
                    if auth_token and ":" in auth_token:
                        parts = auth_token.split(":", 1)
                        self.login_id = parts[0]
                        self.password = parts[1]

            if not self.login_id or not self.password:
                return {"status": "error", "message": "Evermore credentials not found"}

            use_uat = os.getenv("EVERMORE_USE_UAT", "false").lower() == "true"

            # Initialize WebSocket client
            self.ws_client = EvermoreWebSocket(
                login_id=self.login_id,
                password=self.password,
                on_market_data=self._handle_market_data,
                on_depth_data=self._handle_depth_data,
                on_index_data=self._handle_index_data,
                on_greek_data=self._handle_greek_data,
                use_uat=use_uat,
            )

            # Set connection callbacks
            self.ws_client.on_connect = self._on_connect
            self.ws_client.on_disconnect = self._on_disconnect
            self.ws_client.on_error = self._on_error

            self.logger.info(f"Evermore adapter initialized for user {user_id}")
            return {"status": "success", "message": "Adapter initialized successfully"}

        except Exception as e:
            self.logger.error(f"Error initializing adapter: {e}")
            return {"status": "error", "message": str(e)}

    def connect(self) -> Dict[str, Any]:
        """Connect to Evermore WebSocket"""
        if not self.ws_client:
            return {"status": "error", "message": "WebSocket client not initialized"}

        try:
            with self.lock:
                if self.running and self.connected:
                    return {"status": "success", "message": "Already connected"}

                if self.ws_client.start():
                    self.running = True

                    self.logger.info("Waiting for Evermore WebSocket connection...")
                    if self.ws_client.wait_for_connection(timeout=15.0):
                        self.connected = True
                        self.logger.info("Evermore WebSocket connected successfully")
                        return {"status": "success", "message": "Connected successfully"}
                    else:
                        if self.ws_client.running:
                            return {
                                "status": "success",
                                "message": "Client started, connection in progress",
                            }
                        return {"status": "error", "message": "Connection timeout"}
                else:
                    return {"status": "error", "message": "Failed to start WebSocket client"}

        except Exception as e:
            self.logger.error(f"Error connecting: {e}")
            return {"status": "error", "message": str(e)}

    def disconnect(self) -> Dict[str, Any]:
        """Disconnect from WebSocket and clean up resources"""
        try:
            # Cancel pending batch timer
            if self.batch_timer:
                self.batch_timer.cancel()
                self.batch_timer = None

            with self.lock:
                if self.ws_client:
                    self.ws_client.stop()
                    self.ws_client = None

                self.running = False
                self.connected = False
                self.reconnect_attempts = 0
                self.subscribed_symbols.clear()
                self.token_to_symbol.clear()

            self.cleanup_zmq()
            self.logger.info("Evermore WebSocket disconnected")

            return {
                "status": "success",
                "message": "Disconnected successfully and resources cleaned up",
            }

        except Exception as e:
            self.logger.error(f"Error disconnecting: {e}")
            try:
                self.cleanup_zmq()
            except Exception:
                pass
            return {"status": "error", "message": str(e)}

    def subscribe(
        self, symbol: str, exchange: str, mode: int = 2, depth_level: int = 5
    ) -> Dict[str, Any]:
        """
        Subscribe to market data for a symbol.

        Args:
            symbol: Trading symbol (e.g., 'RELIANCE', 'NIFTY')
            exchange: Exchange code (e.g., 'NSE', 'NSE_INDEX', 'NFO')
            mode: Subscription mode (1=LTP, 2=Quote, 3=Depth)
            depth_level: Market depth level (5 supported)
        """
        if not self.ws_client:
            return {"status": "error", "message": "WebSocket client not initialized"}

        if not self.running:
            return {"status": "error", "message": "WebSocket not connected. Call connect() first."}

        try:
            # Get instrument token from database
            token_data = get_token(symbol, exchange)
            if not token_data:
                return {"status": "error", "message": f"Token not found for {symbol} on {exchange}"}

            # Extract token string
            if isinstance(token_data, dict):
                token = str(token_data.get("token", ""))
            elif isinstance(token_data, str):
                # Handle formats like "738561::::2885"
                if "::::" in token_data:
                    token = token_data.split("::::")[0]
                elif ":" in token_data:
                    token = token_data.split(":")[0]
                else:
                    token = token_data
            else:
                token = str(token_data)

            if not token:
                return {"status": "error", "message": f"Invalid token for {symbol}"}

            # Check connection
            if not self.ws_client.is_connected():
                self.logger.warning("WebSocket not connected, waiting...")
                if not self.ws_client.wait_for_connection(timeout=10.0):
                    return {"status": "error", "message": "WebSocket connection timeout"}

            # Map exchange for subscriptions
            evermore_xchg = EvermoreExchangeMapper.to_evermore_exchange(exchange)

            # Add to batch queue and track subscription atomically
            key = f"{exchange}:{symbol}"
            with self.lock:
                self.subscription_queue.append({
                    "token": token,
                    "symbol": symbol,
                    "exchange": exchange,
                    "evermore_xchg": evermore_xchg,
                    "mode": mode,
                    "depth_level": depth_level,
                })

                if len(self.subscription_queue) == 1:
                    self._start_batch_timer()

                self.subscribed_symbols[key] = {
                    "exchange": exchange,
                    "symbol": symbol,
                    "token": token,
                    "mode": mode,
                    "evermore_xchg": evermore_xchg,
                }
                self.token_to_symbol[f"{evermore_xchg}:{token}"] = (symbol, exchange)

            self.logger.info(
                f"Subscribed to {exchange}:{symbol} (token: {token}, mode: {mode})"
            )
            return {"status": "success", "message": f"Subscribed to {symbol}"}

        except Exception as e:
            self.logger.error(f"Error subscribing to {exchange}:{symbol}: {e}")
            return {"status": "error", "message": str(e)}

    def unsubscribe(
        self, symbol: str, exchange: str, mode: int = 2, depth_level: int = None
    ) -> Dict[str, Any]:
        """Unsubscribe from market data for a symbol"""
        try:
            key = f"{exchange}:{symbol}"

            with self.lock:
                if key not in self.subscribed_symbols:
                    return {"status": "error", "message": f"Not subscribed to {symbol}"}

                sub = self.subscribed_symbols[key]
                token = sub["token"]
                evermore_xchg = sub["evermore_xchg"]
                sub_mode = sub["mode"]

            # Determine feed types to unsubscribe
            feed_types = self._get_feed_types_for_mode(sub_mode)

            # Send unsubscribe for each feed type
            quote = {"Xchg": evermore_xchg, "Tkn": token, "Symbol": symbol}
            if self.ws_client and self.ws_client.is_connected():
                for ft in feed_types:
                    self.ws_client.unsubscribe([quote], feed_type=ft)

            # Remove from tracking
            with self.lock:
                del self.subscribed_symbols[key]
                self.token_to_symbol.pop(f"{evermore_xchg}:{token}", None)

            self.logger.info(f"Unsubscribed from {exchange}:{symbol}")
            return {"status": "success", "message": f"Unsubscribed from {symbol}"}

        except Exception as e:
            self.logger.error(f"Error unsubscribing from {exchange}:{symbol}: {e}")
            return {"status": "error", "message": str(e)}

    # =========================================================================
    # Batch Subscription
    # =========================================================================

    def _start_batch_timer(self):
        """Start a timer to process batch subscriptions"""
        if self.batch_timer:
            self.batch_timer.cancel()
        self.batch_timer = threading.Timer(self.batch_delay, self._process_batch_subscriptions)
        self.batch_timer.start()

    def _process_batch_subscriptions(self):
        """Process queued subscriptions grouped by exchange and feed type"""
        with self.lock:
            if not self.subscription_queue:
                return
            queue = list(self.subscription_queue)
            self.subscription_queue.clear()

        # Group by (evermore_xchg, feed_type)
        groups: Dict[tuple, list] = {}
        for sub in queue:
            feed_types = self._get_feed_types_for_mode(sub["mode"])
            for ft in feed_types:
                group_key = (sub["evermore_xchg"], ft)
                if group_key not in groups:
                    groups[group_key] = []
                groups[group_key].append({
                    "Xchg": sub["evermore_xchg"],
                    "Tkn": sub["token"],
                    "Symbol": sub["symbol"],
                })

        # Send subscriptions
        for (xchg, feed_type), quotes in groups.items():
            try:
                self.logger.info(
                    f"Batch subscribing {len(quotes)} instruments on {xchg}, FeedType={feed_type}"
                )
                self.ws_client.subscribe(quotes, feed_type=feed_type)
            except Exception as e:
                self.logger.error(f"Batch subscription failed for {xchg}/FT{feed_type}: {e}")

    def _get_feed_types_for_mode(self, mode: int) -> list:
        """
        Map OpenAlgo mode to Evermore FeedType(s).

        Mode 1 (LTP) -> FeedType 1 (MarketData)
        Mode 2 (Quote) -> FeedType 1 (MarketData)
        Mode 3 (Depth) -> FeedType 1 + FeedType 2 (MarketData + Depth)
        """
        if mode == 3:
            return [1, 2]  # Need both MarketData and Depth
        return [1]  # MarketData covers both LTP and Quote

    # =========================================================================
    # Data Handlers (callbacks from EvermoreWebSocket)
    # =========================================================================

    def _handle_market_data(self, data: dict):
        """
        Handle MarketData message from Evermore.

        Evermore MarketData fields:
            Xchg, Tkn, LTP, LTQ, LUT, LTT, ATP, BQ, BP, SQ, SP,
            TBQ, TSQ, TTQ, TTV, OI, O, H, L, C, DPRL, DPRH
        """
        try:
            xchg = data.get("Xchg", "")
            tkn = str(data.get("Tkn", ""))
            lookup_key = f"{xchg}:{tkn}"

            symbol_info = self.token_to_symbol.get(lookup_key)
            if not symbol_info:
                self.logger.debug(f"No subscription for {lookup_key}")
                return

            symbol, oa_exchange = symbol_info

            # Find all modes this symbol is subscribed to
            key = f"{oa_exchange}:{symbol}"
            with self.lock:
                sub = self.subscribed_symbols.get(key)
                if not sub:
                    return
                sub_mode = sub["mode"]

            timestamp = int(time.time() * 1000)
            ltt = data.get("LTT", "")

            # Build full quote data (Evermore MarketData has everything)
            quote_data = {
                "symbol": symbol,
                "exchange": oa_exchange,
                "ltp": float(data.get("LTP", 0)),
                "ltt": ltt,
                "timestamp": timestamp,
                "volume": float(data.get("TTQ", 0)),
                "last_quantity": float(data.get("LTQ", 0)),
                "average_price": float(data.get("ATP", 0)),
                "total_buy_quantity": float(data.get("TBQ", 0)),
                "total_sell_quantity": float(data.get("TSQ", 0)),
                "best_bid_price": float(data.get("BP", 0)),
                "best_bid_quantity": float(data.get("BQ", 0)),
                "best_ask_price": float(data.get("SP", 0)),
                "best_ask_quantity": float(data.get("SQ", 0)),
                "open": float(data.get("O", 0)),
                "high": float(data.get("H", 0)),
                "low": float(data.get("L", 0)),
                "close": float(data.get("C", 0)),
                "oi": float(data.get("OI", 0)),
                "lower_circuit": float(data.get("DPRL", 0)),
                "upper_circuit": float(data.get("DPRH", 0)),
            }

            # Publish based on subscribed mode
            if sub_mode == 1:
                # LTP only
                ltp_data = {
                    "symbol": symbol,
                    "exchange": oa_exchange,
                    "mode": "ltp",
                    "ltp": quote_data["ltp"],
                    "ltt": ltt,
                    "timestamp": timestamp,
                }
                topic = f"{oa_exchange}_{symbol}_LTP"
                self.publish_market_data(topic, ltp_data)

            elif sub_mode == 2:
                # Quote (full market data without depth)
                quote_data["mode"] = "quote"
                topic = f"{oa_exchange}_{symbol}_QUOTE"
                self.publish_market_data(topic, quote_data)

            elif sub_mode == 3:
                # Depth mode: publish quote data too, depth comes from _handle_depth_data
                quote_data["mode"] = "quote"
                topic = f"{oa_exchange}_{symbol}_QUOTE"
                self.publish_market_data(topic, quote_data)

        except Exception as e:
            self.logger.error(f"Error handling market data: {e}", exc_info=True)

    def _handle_depth_data(self, data: dict):
        """
        Handle Depth message from Evermore.

        Evermore Depth fields:
            Xchg, Tkn, Depths[] where each depth level has:
            BO (bid orders), BP (bid price), BQ (bid qty),
            SQ (ask qty), SP (ask price), SO (ask orders)
        """
        try:
            xchg = data.get("Xchg", "")
            tkn = str(data.get("Tkn", ""))
            lookup_key = f"{xchg}:{tkn}"

            symbol_info = self.token_to_symbol.get(lookup_key)
            if not symbol_info:
                return

            symbol, oa_exchange = symbol_info
            timestamp = int(time.time() * 1000)

            # Parse depth levels
            depths = data.get("Depths", [])
            buy_depth = []
            sell_depth = []

            for level in depths:
                buy_depth.append({
                    "price": float(level.get("BP", 0)),
                    "quantity": float(level.get("BQ", 0)),
                    "orders": int(level.get("BO", 0)),
                })
                sell_depth.append({
                    "price": float(level.get("SP", 0)),
                    "quantity": float(level.get("SQ", 0)),
                    "orders": int(level.get("SO", 0)),
                })

            depth_data = {
                "symbol": symbol,
                "exchange": oa_exchange,
                "mode": "full",
                "timestamp": timestamp,
                "depth": {
                    "buy": buy_depth[:5],
                    "sell": sell_depth[:5],
                },
            }

            topic = f"{oa_exchange}_{symbol}_DEPTH"
            self.publish_market_data(topic, depth_data)

        except Exception as e:
            self.logger.error(f"Error handling depth data: {e}", exc_info=True)

    def _handle_index_data(self, data: dict):
        """
        Handle IndexData message from Evermore.

        Evermore IndexData fields:
            Symbol, Price, O, H, L, C
        """
        try:
            index_symbol = data.get("Symbol", "")
            if not index_symbol:
                return

            # Try to find matching subscription for index
            # Index subscriptions use NSE_INDEX or BSE_INDEX exchange
            symbol_info = None
            for key, (sym, exch) in self.token_to_symbol.items():
                if sym == index_symbol and exch in ("NSE_INDEX", "BSE_INDEX"):
                    symbol_info = (sym, exch)
                    break

            if not symbol_info:
                self.logger.debug(f"No subscription for index: {index_symbol}")
                return

            symbol, oa_exchange = symbol_info
            timestamp = int(time.time() * 1000)

            # Find the subscribed mode
            sub_key = f"{oa_exchange}:{symbol}"
            with self.lock:
                sub = self.subscribed_symbols.get(sub_key)
                if not sub:
                    return
                sub_mode = sub["mode"]

            index_data = {
                "symbol": symbol,
                "exchange": oa_exchange,
                "ltp": float(data.get("Price", 0)),
                "open": float(data.get("O", 0)),
                "high": float(data.get("H", 0)),
                "low": float(data.get("L", 0)),
                "close": float(data.get("C", 0)),
                "timestamp": timestamp,
            }

            if sub_mode == 1:
                ltp_data = {
                    "symbol": symbol,
                    "exchange": oa_exchange,
                    "mode": "ltp",
                    "ltp": index_data["ltp"],
                    "timestamp": timestamp,
                }
                topic = f"{oa_exchange}_{symbol}_LTP"
                self.publish_market_data(topic, ltp_data)
            else:
                index_data["mode"] = "quote"
                topic = f"{oa_exchange}_{symbol}_QUOTE"
                self.publish_market_data(topic, index_data)

        except Exception as e:
            self.logger.error(f"Error handling index data: {e}", exc_info=True)

    def _handle_greek_data(self, data: dict):
        """
        Handle Greek market data from Evermore (for options).
        Includes all MarketData fields plus: SpotPrice, IV, Delta, Gamma, Theta, Vega, Rho, Depths
        Published as quote data with greeks appended.
        """
        try:
            xchg = data.get("Xchg", "")
            tkn = str(data.get("Tkn", ""))
            lookup_key = f"{xchg}:{tkn}"

            symbol_info = self.token_to_symbol.get(lookup_key)
            if not symbol_info:
                return

            symbol, oa_exchange = symbol_info
            timestamp = int(time.time() * 1000)

            greek_data = {
                "symbol": symbol,
                "exchange": oa_exchange,
                "mode": "quote",
                "ltp": float(data.get("LTP", 0)),
                "ltt": data.get("LTT", ""),
                "timestamp": timestamp,
                "volume": float(data.get("TTQ", 0)),
                "open": float(data.get("O", 0)),
                "high": float(data.get("H", 0)),
                "low": float(data.get("L", 0)),
                "close": float(data.get("C", 0)),
                "oi": float(data.get("OI", 0)),
                "spot_price": float(data.get("SpotPrice", 0)),
                "iv": float(data.get("IV", 0)),
                "delta": float(data.get("Delta", 0)),
                "gamma": float(data.get("Gamma", 0)),
                "theta": float(data.get("Theta", 0)),
                "vega": float(data.get("Vega", 0)),
                "rho": float(data.get("Rho", 0)),
            }

            topic = f"{oa_exchange}_{symbol}_QUOTE"
            self.publish_market_data(topic, greek_data)

        except Exception as e:
            self.logger.error(f"Error handling greek data: {e}", exc_info=True)

    # =========================================================================
    # Connection Callbacks
    # =========================================================================

    def _on_connect(self):
        """Handle WebSocket connection established"""
        self.connected = True
        self.reconnect_attempts = 0
        self.logger.info("Evermore WebSocket connected")

    def _on_disconnect(self):
        """Handle WebSocket disconnection"""
        self.connected = False
        self.logger.warning("Evermore WebSocket disconnected")

    def _on_error(self, error):
        """Handle WebSocket errors"""
        self.logger.error(f"Evermore WebSocket error: {error}")

    # =========================================================================
    # Utility
    # =========================================================================

    def get_subscriptions(self) -> Dict[str, Any]:
        """Get current subscriptions"""
        with self.lock:
            return {
                "status": "success",
                "subscriptions": list(self.subscribed_symbols.keys()),
                "count": len(self.subscribed_symbols),
            }

    def is_connected(self) -> bool:
        """Check if WebSocket is connected"""
        return self.connected and self.running

    def cleanup(self):
        """Clean up all resources"""
        try:
            if self.batch_timer:
                self.batch_timer.cancel()
                self.batch_timer = None

            with self.lock:
                if self.ws_client:
                    try:
                        self.ws_client.stop()
                    except Exception:
                        pass
                    self.ws_client = None

                self.running = False
                self.connected = False
                self.subscribed_symbols.clear()
                self.token_to_symbol.clear()

            self.cleanup_zmq()
            self.logger.info("Evermore adapter cleaned up completely")

        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
            try:
                self.cleanup_zmq()
            except Exception:
                pass

    def __del__(self):
        """Destructor - ensures resources are released"""
        try:
            self.cleanup()
        except Exception:
            pass
