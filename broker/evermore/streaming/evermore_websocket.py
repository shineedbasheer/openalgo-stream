"""
Evermore WebSocket client for the MT Data Feed API.

Handles the JSON-based WebSocket protocol including:
- Login/Logout
- Token subscription/unsubscription (MarketData, Depth, Greeks)
- Heartbeat keep-alive
- Automatic reconnection with exponential backoff

Protocol reference: MT.Data.Feed.API_V1.pdf
WebSocket endpoints:
  Live: wss://feedapi.com
  UAT:  ws://115.242.15.134:19101
"""

import json
import os
import threading
import time
from typing import Any, Callable, Dict, List, Optional

import websocket

from utils.logging import get_logger


class EvermoreWebSocket:
    """WebSocket client for Evermore MT Data Feed API"""

    # Default endpoints
    LIVE_URL = "wss://feedapi.com"
    UAT_URL = "ws://115.242.15.134:19101"

    def __init__(
        self,
        login_id: str,
        password: str,
        on_market_data: Optional[Callable] = None,
        on_depth_data: Optional[Callable] = None,
        on_index_data: Optional[Callable] = None,
        on_greek_data: Optional[Callable] = None,
        use_uat: bool = False,
    ):
        self.logger = get_logger("evermore_ws_client")
        self.login_id = login_id
        self.password = password
        self.use_uat = use_uat

        # Callbacks
        self.on_market_data = on_market_data
        self.on_depth_data = on_depth_data
        self.on_index_data = on_index_data
        self.on_greek_data = on_greek_data
        self.on_connect: Optional[Callable] = None
        self.on_disconnect: Optional[Callable] = None
        self.on_error: Optional[Callable] = None

        # State
        self.ws: Optional[websocket.WebSocketApp] = None
        self.ws_thread: Optional[threading.Thread] = None
        self.heartbeat_thread: Optional[threading.Thread] = None
        self.running = False
        self.connected = False
        self.logged_in = False
        self.allowed_exchanges: List[str] = []
        self.lock = threading.Lock()
        self._connection_event = threading.Event()

        # Reconnection
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        self.reconnect_delay = 5
        self.max_reconnect_delay = 60

        # Heartbeat interval (seconds) - Evermore requires HB every minute
        self.heartbeat_interval = 50  # Send slightly before the 60s deadline

        # Track subscriptions for resubscription on reconnect
        self._subscriptions: List[Dict] = []  # list of TokenRequest Data objects

    @property
    def url(self) -> str:
        if self.use_uat:
            return os.getenv("EVERMORE_UAT_URL", self.UAT_URL)
        return os.getenv("EVERMORE_LIVE_URL", self.LIVE_URL)

    def start(self) -> bool:
        """Start the WebSocket connection in a background thread"""
        if self.running:
            self.logger.warning("WebSocket client already running")
            return True

        self.running = True
        self._connection_event.clear()

        self.ws = websocket.WebSocketApp(
            self.url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )

        self.ws_thread = threading.Thread(
            target=self._run_ws, daemon=True, name="evermore-ws"
        )
        self.ws_thread.start()

        self.logger.info(f"WebSocket client starting, connecting to {self.url}")
        return True

    def _run_ws(self):
        """Run the WebSocket event loop"""
        try:
            self.ws.run_forever(
                ping_interval=30,
                ping_timeout=10,
                reconnect=0,  # We handle reconnection ourselves
            )
        except Exception as e:
            self.logger.error(f"WebSocket run_forever error: {e}")
        finally:
            self.connected = False
            self.logged_in = False

    def stop(self):
        """Stop the WebSocket connection and clean up"""
        # Send logout before changing state flags
        if self.ws and self.connected:
            try:
                self._send_message("Logout", "logout")
            except Exception:
                pass

        self.running = False
        self.connected = False
        self.logged_in = False
        self._connection_event.set()

        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass
            self.ws = None

        self.logger.info("WebSocket client stopped")

    def wait_for_connection(self, timeout: float = 15.0) -> bool:
        """Wait for the WebSocket to connect and login"""
        return self._connection_event.wait(timeout=timeout)

    def is_connected(self) -> bool:
        return self.connected and self.logged_in

    # =========================================================================
    # Protocol Messages
    # =========================================================================

    def _send_message(self, msg_type: str, data: Any):
        """Send a JSON message to the WebSocket server"""
        if not self.ws:
            self.logger.warning("Cannot send message - WebSocket not initialized")
            return

        message = {"Type": msg_type, "Data": data}
        try:
            self.ws.send(json.dumps(message))
            self.logger.debug(f"Sent: {msg_type}")
        except Exception as e:
            self.logger.error(f"Error sending {msg_type}: {e}")

    def _send_login(self):
        """Send login request"""
        self._send_message("Login", {
            "LoginId": self.login_id,
            "Password": self.password,
        })

    def _send_heartbeat(self):
        """Send heartbeat to keep connection alive"""
        self._send_message("Info", {
            "InfoType": "HB",
            "InfoMsg": "",
        })

    def subscribe(self, quotes: List[Dict], feed_type: int = 1):
        """
        Subscribe to market data for given instruments.

        Args:
            quotes: List of {"Xchg": "NSECM", "Tkn": "2885", "Symbol": "RELIANCE"}
            feed_type: 1=MarketData, 2=Depth, 3=SnapQuote, 4=Greeks
        """
        data = {
            "SubType": True,
            "FeedType": feed_type,
            "quotes": quotes,
        }
        self._send_message("TokenRequest", data)

        # Track for resubscription on reconnect (deduplicate by feed_type + tokens)
        with self.lock:
            # Remove any existing subscription with same feed_type and quotes
            self._subscriptions = [
                s for s in self._subscriptions
                if not (s["FeedType"] == feed_type and s["quotes"] == quotes)
            ]
            self._subscriptions.append(data)

        self.logger.info(
            f"Subscribe sent: {len(quotes)} instruments, FeedType={feed_type}"
        )

    def unsubscribe(self, quotes: List[Dict], feed_type: int = 1):
        """
        Unsubscribe from market data.

        Args:
            quotes: List of {"Xchg": "NSECM", "Tkn": "2885", "Symbol": "RELIANCE"}
            feed_type: 1=MarketData, 2=Depth, 3=SnapQuote, 4=Greeks
        """
        data = {
            "SubType": False,
            "FeedType": feed_type,
            "quotes": quotes,
        }
        self._send_message("TokenRequest", data)

        # Remove from tracked subscriptions
        with self.lock:
            self._subscriptions = [
                s for s in self._subscriptions
                if not (s["FeedType"] == feed_type and s["quotes"] == quotes)
            ]

        self.logger.info(
            f"Unsubscribe sent: {len(quotes)} instruments, FeedType={feed_type}"
        )

    # =========================================================================
    # WebSocket Callbacks
    # =========================================================================

    def _on_open(self, ws):
        """Called when WebSocket connection is established"""
        self.logger.info("WebSocket connection opened, sending login...")
        self.connected = True
        self._send_login()

    def _on_message(self, ws, message: str):
        """Handle incoming JSON messages from the server"""
        try:
            msg = json.loads(message)
        except json.JSONDecodeError:
            self.logger.warning(f"Non-JSON message received: {message[:200]}")
            return

        msg_type = msg.get("Type", "")
        data = msg.get("Data", {})

        if msg_type == "Login":
            self._handle_login_response(data)
        elif msg_type == "Logout":
            self._handle_logout_response(data)
        elif msg_type == "MarketData":
            self._handle_market_data(data)
        elif msg_type == "Depth":
            self._handle_depth_data(data)
        elif msg_type == "IndexData":
            self._handle_index_data(data)
        elif msg_type == "Greek":
            self._handle_greek_data(data)
        elif msg_type == "FeedStatus":
            self._handle_feed_status(data)
        elif msg_type == "Info":
            self._handle_info(data)
        elif msg_type == "Error":
            self.logger.error(f"Server error: {data}")
        elif msg_type == "OChain":
            self.logger.debug(f"Option chain data received")
        elif msg_type == "CandleBar":
            self.logger.debug(f"Candle bar data received")
        else:
            self.logger.debug(f"Unhandled message type: {msg_type}")

    def _on_error(self, ws, error):
        """Called on WebSocket error"""
        self.logger.error(f"WebSocket error: {error}")
        if self.on_error:
            self.on_error(error)

    def _on_close(self, ws, close_status_code, close_msg):
        """Called when WebSocket connection is closed"""
        self.connected = False
        self.logged_in = False
        self.logger.warning(
            f"WebSocket closed: status={close_status_code}, msg={close_msg}"
        )

        if self.on_disconnect:
            self.on_disconnect()

        # Attempt reconnection if still running (in a new thread to avoid blocking)
        if self.running:
            threading.Thread(
                target=self._reconnect, daemon=True, name="evermore-reconnect"
            ).start()

    # =========================================================================
    # Message Handlers
    # =========================================================================

    def _handle_login_response(self, data: dict):
        """Handle login response"""
        error = data.get("Error", "")
        if error:
            self.logger.error(f"Login failed: {error}")
            self.logged_in = False
            if self.on_error:
                self.on_error(f"Login failed: {error}")
            return

        self.logged_in = True
        self.reconnect_attempts = 0

        # Parse allowed exchanges
        xchgs = data.get("Xchgs", "")
        if xchgs:
            self.allowed_exchanges = [x.strip() for x in xchgs.split(",") if x.strip()]

        version = data.get("Version", "unknown")
        self.logger.info(
            f"Login successful. Version={version}, Exchanges={self.allowed_exchanges}"
        )

        # Signal connection ready
        self._connection_event.set()

        # Start heartbeat thread
        self._start_heartbeat()

        # Resubscribe to existing subscriptions (on reconnect)
        self._resubscribe()

        if self.on_connect:
            self.on_connect()

    def _handle_logout_response(self, data):
        """Handle logout response"""
        self.logged_in = False
        self.logger.info(f"Logged out: {data}")

    def _handle_market_data(self, data: dict):
        """Forward market data to callback"""
        if self.on_market_data:
            self.on_market_data(data)

    def _handle_depth_data(self, data: dict):
        """Forward depth data to callback"""
        if self.on_depth_data:
            self.on_depth_data(data)

    def _handle_index_data(self, data):
        """Forward index data to callback"""
        if self.on_index_data:
            # IndexData comes as an array
            if isinstance(data, list):
                for item in data:
                    self.on_index_data(item)
            else:
                self.on_index_data(data)

    def _handle_greek_data(self, data: dict):
        """Forward greek data to callback"""
        if self.on_greek_data:
            self.on_greek_data(data)

    def _handle_feed_status(self, data):
        """Handle feed status updates"""
        if isinstance(data, list):
            for status in data:
                xchg = status.get("Xchg", "")
                connected = status.get("Status", 0) == 1
                self.logger.info(
                    f"Feed status: {xchg} = {'Connected' if connected else 'Disconnected'}"
                )
        else:
            self.logger.info(f"Feed status: {data}")

    def _handle_info(self, data):
        """Handle informational messages"""
        if isinstance(data, dict):
            info_type = data.get("InfoType", "")
            info_msg = data.get("InfoMsg", "")
            if info_type == "Error":
                self.logger.error(f"Server info error: {info_msg}")
            elif info_type == "Warning":
                self.logger.warning(f"Server warning: {info_msg}")
            elif info_type in ("XchgMsg", "BrkMsg"):
                self.logger.info(f"{info_type}: {info_msg}")
            # Ignore HB responses
        else:
            self.logger.debug(f"Info: {data}")

    # =========================================================================
    # Heartbeat & Reconnection
    # =========================================================================

    def _start_heartbeat(self):
        """Start the heartbeat thread"""
        if self.heartbeat_thread and self.heartbeat_thread.is_alive():
            return

        self.heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, daemon=True, name="evermore-hb"
        )
        self.heartbeat_thread.start()
        self.logger.debug("Heartbeat thread started")

    def _heartbeat_loop(self):
        """Send periodic heartbeats to keep the connection alive"""
        while self.running and self.connected and self.logged_in:
            time.sleep(self.heartbeat_interval)
            if self.running and self.connected and self.logged_in:
                try:
                    self._send_heartbeat()
                    self.logger.debug("Heartbeat sent")
                except Exception as e:
                    self.logger.error(f"Heartbeat error: {e}")
                    break

    def _reconnect(self):
        """Attempt to reconnect with exponential backoff"""
        if not self.running:
            return

        self.reconnect_attempts += 1
        if self.reconnect_attempts > self.max_reconnect_attempts:
            self.logger.error("Max reconnection attempts reached")
            self.running = False
            return

        delay = min(
            self.reconnect_delay * (2 ** (self.reconnect_attempts - 1)),
            self.max_reconnect_delay,
        )
        self.logger.info(
            f"Reconnecting in {delay}s (attempt {self.reconnect_attempts}/{self.max_reconnect_attempts})"
        )
        time.sleep(delay)

        if self.running:
            self._connection_event.clear()

            self.ws = websocket.WebSocketApp(
                self.url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
            )

            self.ws_thread = threading.Thread(
                target=self._run_ws, daemon=True, name="evermore-ws-reconnect"
            )
            self.ws_thread.start()

    def _resubscribe(self):
        """Resubscribe to all tracked subscriptions after reconnect"""
        with self.lock:
            if not self._subscriptions:
                return

            self.logger.info(
                f"Resubscribing to {len(self._subscriptions)} subscription groups"
            )
            subs_copy = list(self._subscriptions)

        for sub_data in subs_copy:
            try:
                self._send_message("TokenRequest", sub_data)
            except Exception as e:
                self.logger.error(f"Resubscription failed: {e}")
