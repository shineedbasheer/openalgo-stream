"""
Evermore WebSocket Client

Low-level WebSocket client for the Evermore Data Feed API.
Handles connection, authentication, subscription, heartbeat, and message dispatch.

Protocol: JSON over WebSocket
Heartbeat: Must send Info HB every 55 seconds
"""

import json
import os
import threading
import time
from collections.abc import Callable
from typing import Any, Dict, List, Optional

from utils.logging import get_logger

logger = get_logger(__name__)


class EvermoreWebSocket:
    """
    Low-level WebSocket client for Evermore Data Feed API.

    Usage:
        ws = EvermoreWebSocket(login_id="DAKS", password="xxx", url="ws://...")
        ws.on_tick = my_tick_handler
        ws.on_connect = my_connect_handler
        ws.connect()
        ws.subscribe([{"Xchg": "NSECM", "Tkn": "2885", "Symbol": "RELIANCE"}], feed_type=1)
        ...
        ws.disconnect()
    """

    def __init__(self, login_id: str, password: str, url: Optional[str] = None):
        self.login_id = login_id
        self.password = password
        self.url = url or os.getenv("EVERMORE_WS_URL", "ws://192.168.6.164:19101")

        self.ws = None
        self.ws_thread = None
        self.heartbeat_thread = None
        self.connected = False
        self.logged_in = False
        self.running = False
        self.lock = threading.Lock()

        # Heartbeat interval (55 seconds — server timeout is 60s)
        self.heartbeat_interval = 55

        # Callbacks
        self.on_tick: Optional[Callable] = None
        self.on_connect: Optional[Callable] = None
        self.on_disconnect: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
        self.on_login: Optional[Callable] = None

        # Track subscriptions for reconnect
        self._subscriptions: Dict[str, Dict] = {}  # key: "exchange:token", value: {feed_type, quotes}

    def connect(self, timeout: float = 15.0):
        """
        Connect to Evermore WebSocket and authenticate.
        Blocks until connected and logged in, or timeout.
        """
        try:
            import websocket
        except ImportError:
            raise ImportError(
                "websocket-client is required for Evermore streaming. "
                "Install it with: pip install websocket-client"
            )

        self.running = True
        connect_event = threading.Event()

        def _on_open(ws_app):
            logger.info(f"Evermore WebSocket connected to {self.url}")
            self.connected = True

            # Send login
            login_msg = json.dumps({
                "Type": "Login",
                "Data": {
                    "LoginId": self.login_id,
                    "Password": self.password,
                }
            })
            ws_app.send(login_msg)
            logger.info("Evermore WebSocket: Login sent")

        def _on_message(ws_app, message):
            try:
                msg = json.loads(message)
                msg_type = msg.get("Type", "")
                msg_data = msg.get("Data", {})

                if msg_type == "Login":
                    error = msg_data.get("Error", "") if isinstance(msg_data, dict) else ""
                    if not error:
                        self.logged_in = True
                        logger.info(
                            f"Evermore WebSocket: Logged in. "
                            f"Exchanges: {msg_data.get('Xchgs', '')}, "
                            f"Version: {msg_data.get('Version', '')}"
                        )
                        # Start heartbeat
                        self._start_heartbeat()
                        connect_event.set()

                        if self.on_login:
                            self.on_login(msg_data)
                        if self.on_connect:
                            self.on_connect()
                    else:
                        logger.error(f"Evermore WebSocket: Login failed: {error}")
                        connect_event.set()
                        if self.on_error:
                            self.on_error(f"Login failed: {error}")

                elif msg_type == "Logout":
                    logger.info(f"Evermore WebSocket: Logout response: {msg_data}")
                    self.logged_in = False

                elif msg_type in ("MarketData", "Depth", "Greek", "IndexData"):
                    if self.on_tick:
                        self.on_tick(msg_type, msg_data)

                elif msg_type == "FeedStatus":
                    logger.info(f"Evermore FeedStatus: {msg_data}")

                elif msg_type == "Info":
                    info_type = msg_data.get("InfoType", "") if isinstance(msg_data, dict) else ""
                    if info_type != "HB":
                        logger.info(f"Evermore Info: {msg_data}")

                elif msg_type == "OChain":
                    if self.on_tick:
                        self.on_tick(msg_type, msg_data)

                elif msg_type == "CandleBar":
                    if self.on_tick:
                        self.on_tick(msg_type, msg_data)

                else:
                    logger.debug(f"Evermore WebSocket: Unknown type '{msg_type}': {str(msg_data)[:200]}")

            except json.JSONDecodeError:
                logger.error(f"Evermore WebSocket: Invalid JSON: {message[:200]}")
            except Exception as e:
                logger.error(f"Evermore WebSocket: Error processing message: {e}")

        def _on_error(ws_app, error):
            logger.error(f"Evermore WebSocket error: {error}")
            if self.on_error:
                self.on_error(str(error))

        def _on_close(ws_app, close_status_code, close_msg):
            logger.info(f"Evermore WebSocket closed: {close_status_code} {close_msg}")
            self.connected = False
            self.logged_in = False
            connect_event.set()
            if self.on_disconnect:
                self.on_disconnect()

        import websocket

        self.ws = websocket.WebSocketApp(
            self.url,
            on_open=_on_open,
            on_message=_on_message,
            on_error=_on_error,
            on_close=_on_close,
        )

        # Run WebSocket in background thread
        self.ws_thread = threading.Thread(
            target=self.ws.run_forever,
            kwargs={"ping_interval": 0},  # We handle heartbeat ourselves
            daemon=True,
        )
        self.ws_thread.start()

        # Wait for login response
        if not connect_event.wait(timeout=timeout):
            logger.error(f"Evermore WebSocket: Connection/login timeout ({timeout}s)")
            self.disconnect()
            return False

        return self.logged_in

    def disconnect(self):
        """Disconnect from Evermore WebSocket."""
        self.running = False
        self._stop_heartbeat()

        if self.ws and self.logged_in:
            try:
                self.ws.send(json.dumps({"Type": "Logout", "Data": "logout"}))
                time.sleep(0.5)  # Brief wait for logout response
            except Exception:
                pass

        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass

        self.connected = False
        self.logged_in = False
        self._subscriptions.clear()
        logger.info("Evermore WebSocket: Disconnected")

    def subscribe(self, quotes: List[Dict], feed_type: int = 1):
        """
        Subscribe to market data.

        Args:
            quotes: List of {"Xchg": "NSECM", "Tkn": "2885", "Symbol": "RELIANCE"}
            feed_type: 1=MarketData, 2=Depth, 3=SnapQuote, 4=Greeks
        """
        if not self.logged_in:
            logger.error("Evermore WebSocket: Cannot subscribe — not logged in")
            return

        msg = json.dumps({
            "Type": "TokenRequest",
            "Data": {
                "SubType": True,
                "FeedType": feed_type,
                "quotes": quotes,
            }
        })

        try:
            self.ws.send(msg)
            # Track subscriptions
            for q in quotes:
                key = f"{q['Xchg']}:{q['Tkn']}"
                self._subscriptions[key] = {"feed_type": feed_type, "quote": q}
            logger.info(f"Evermore WebSocket: Subscribed {len(quotes)} tokens (FeedType={feed_type})")
        except Exception as e:
            logger.error(f"Evermore WebSocket: Subscribe error: {e}")

    def unsubscribe(self, quotes: List[Dict], feed_type: int = 1):
        """
        Unsubscribe from market data.

        Args:
            quotes: List of {"Xchg": "NSECM", "Tkn": "2885", "Symbol": "RELIANCE"}
            feed_type: 1=MarketData, 2=Depth, 3=SnapQuote, 4=Greeks
        """
        if not self.logged_in:
            return

        msg = json.dumps({
            "Type": "TokenRequest",
            "Data": {
                "SubType": False,
                "FeedType": feed_type,
                "quotes": quotes,
            }
        })

        try:
            self.ws.send(msg)
            for q in quotes:
                key = f"{q['Xchg']}:{q['Tkn']}"
                self._subscriptions.pop(key, None)
            logger.info(f"Evermore WebSocket: Unsubscribed {len(quotes)} tokens")
        except Exception as e:
            logger.error(f"Evermore WebSocket: Unsubscribe error: {e}")

    def _start_heartbeat(self):
        """Start heartbeat timer to keep connection alive."""
        self._stop_heartbeat()

        def _heartbeat_loop():
            while self.running and self.logged_in:
                time.sleep(self.heartbeat_interval)
                if self.running and self.logged_in:
                    try:
                        hb_msg = json.dumps({
                            "Type": "Info",
                            "Data": {"InfoType": "HB", "InfoMsg": ""}
                        })
                        self.ws.send(hb_msg)
                        logger.debug("Evermore WebSocket: Heartbeat sent")
                    except Exception as e:
                        logger.error(f"Evermore WebSocket: Heartbeat error: {e}")
                        break

        self.heartbeat_thread = threading.Thread(target=_heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()

    def _stop_heartbeat(self):
        """Stop heartbeat timer."""
        self.running = False
        if self.heartbeat_thread and self.heartbeat_thread.is_alive():
            self.heartbeat_thread.join(timeout=2)
        self.heartbeat_thread = None
