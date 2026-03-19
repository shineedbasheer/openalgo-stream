# Evermore (AutoTradeTech) Market Data API
# Evermore has no REST-based quotes/historical API.
# Quotes are fetched via WebSocket snapshot connections.

import json
import os
import threading
import time

from broker.evermore.api.auth_api import get_evermore_auth
from broker.evermore.mapping.transform_data import map_exchange
from database.token_db import get_br_symbol, get_token
from utils.logging import get_logger

logger = get_logger(__name__)


class BrokerData:
    """
    Market data provider for Evermore broker.

    Since Evermore has no REST quotes API, quotes are fetched via
    a temporary WebSocket connection (subscribe → get first tick → disconnect).
    """

    # Market timings for Evermore exchanges
    MARKET_TIMINGS = {
        "NSE": {"start": "09:15:00", "end": "15:30:00"},
        "NFO": {"start": "09:15:00", "end": "15:30:00"},
        "BSE": {"start": "09:15:00", "end": "15:30:00"},
        "BFO": {"start": "09:15:00", "end": "15:30:00"},
        "CDS": {"start": "09:00:00", "end": "17:00:00"},
        "BCD": {"start": "09:00:00", "end": "17:00:00"},
    }

    def __init__(self, auth_token):
        self.auth_token = auth_token
        self.creds = get_evermore_auth(auth_token)
        self.ws_url = os.getenv("EVERMORE_WS_URL", "ws://192.168.6.164:19101")

    def _ws_snapshot(self, symbol, exchange, feed_type=1, timeout=10):
        """
        Connect to Evermore WebSocket, subscribe, get one tick, disconnect.

        Args:
            symbol: Trading symbol
            exchange: OpenAlgo exchange code
            feed_type: 1=MarketData, 2=Depth, 4=Greeks
            timeout: Max seconds to wait for data

        Returns:
            dict: First received data message, or None
        """
        try:
            import websocket as ws_lib
        except ImportError:
            # Fallback to websocket-client
            try:
                from websockets.sync.client import connect as ws_connect
                return self._ws_snapshot_websockets(symbol, exchange, feed_type, timeout)
            except ImportError:
                logger.error("No WebSocket library available. Install websocket-client or websockets.")
                return None

        token = get_token(symbol, exchange)
        evermore_exchange = map_exchange(exchange)
        br_symbol = get_br_symbol(symbol, exchange) or symbol

        result = {"data": None}

        def on_message(ws_app, message):
            try:
                msg = json.loads(message)
                msg_type = msg.get("Type", "")

                if msg_type == "Login":
                    # Login successful, subscribe
                    if not msg.get("Data", {}).get("Error"):
                        subscribe_msg = json.dumps({
                            "Type": "TokenRequest",
                            "Data": {
                                "SubType": True,
                                "FeedType": feed_type,
                                "quotes": [{
                                    "Xchg": evermore_exchange,
                                    "Tkn": str(token),
                                    "Symbol": br_symbol,
                                }]
                            }
                        })
                        ws_app.send(subscribe_msg)

                elif msg_type in ("MarketData", "Depth", "Greek"):
                    data = msg.get("Data", {})
                    if str(data.get("Tkn", "")) == str(token):
                        result["data"] = data
                        ws_app.close()

            except Exception as e:
                logger.error(f"WS snapshot on_message error: {e}")

        def on_open(ws_app):
            login_msg = json.dumps({
                "Type": "Login",
                "Data": {
                    "LoginId": os.getenv("BROKER_API_KEY", ""),
                    "Password": os.getenv("BROKER_API_SECRET", ""),
                }
            })
            ws_app.send(login_msg)

        def on_error(ws_app, error):
            logger.error(f"WS snapshot error: {error}")

        ws_app = ws_lib.WebSocketApp(
            self.ws_url,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
        )

        # Run in thread with timeout
        ws_thread = threading.Thread(target=ws_app.run_forever)
        ws_thread.daemon = True
        ws_thread.start()
        ws_thread.join(timeout=timeout)

        if ws_thread.is_alive():
            ws_app.close()

        return result["data"]

    def get_quotes(self, symbol, exchange):
        """
        Get real-time quote for a single symbol via WebSocket snapshot.

        Returns:
            dict: Quote data with keys matching OpenAlgo format
        """
        data = self._ws_snapshot(symbol, exchange, feed_type=1, timeout=10)

        if not data:
            return {
                "status": "error",
                "message": f"No quote data received for {symbol} on {exchange}",
            }

        return {
            "status": "success",
            "data": {
                "ltp": float(data.get("LTP", 0)),
                "open": float(data.get("O", 0)),
                "high": float(data.get("H", 0)),
                "low": float(data.get("L", 0)),
                "close": float(data.get("C", 0)),
                "volume": int(float(data.get("TTQ", 0))),
                "bid_price": float(data.get("BP", 0)),
                "ask_price": float(data.get("SP", 0)),
                "bid_qty": int(float(data.get("BQ", 0))),
                "ask_qty": int(float(data.get("SQ", 0))),
                "total_buy_qty": int(float(data.get("TBQ", 0))),
                "total_sell_qty": int(float(data.get("TSQ", 0))),
                "atp": float(data.get("ATP", 0)),
                "oi": int(float(data.get("OI", 0))),
                "prev_close": float(data.get("C", 0)),
                "exchange": exchange,
                "symbol": symbol,
            },
        }

    def get_market_depth(self, symbol, exchange):
        """
        Get 5-level market depth via WebSocket snapshot.

        Returns:
            dict: Depth data with buy/sell arrays
        """
        data = self._ws_snapshot(symbol, exchange, feed_type=2, timeout=10)

        if not data:
            return {
                "status": "error",
                "message": f"No depth data received for {symbol} on {exchange}",
            }

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

        return {
            "status": "success",
            "data": {
                "buy": buy_depth,
                "sell": sell_depth,
                "exchange": exchange,
                "symbol": symbol,
            },
        }

    def get_depth(self, symbol, exchange):
        """Alias for get_market_depth."""
        return self.get_market_depth(symbol, exchange)

    def get_history(self, symbol, exchange, timeframe, from_date, to_date):
        """
        Evermore does not provide a historical data API.
        Returns error response.
        """
        return {
            "status": "error",
            "message": "Historical data is not available via Evermore API. "
                       "Use an alternative data source for historical candles.",
        }

    def get_multiquotes(self, symbols):
        """
        Get quotes for multiple symbols.
        Since Evermore has no batch REST quotes, this fetches sequentially.

        Args:
            symbols: list of (symbol, exchange) tuples

        Returns:
            dict: Multi-quote response
        """
        results = {}
        for symbol, exchange in symbols:
            try:
                quote = self.get_quotes(symbol, exchange)
                if quote.get("status") == "success":
                    results[f"{exchange}:{symbol}"] = quote["data"]
            except Exception as e:
                logger.error(f"Error fetching quote for {symbol}:{exchange}: {e}")

        return {"status": "success", "data": results}
