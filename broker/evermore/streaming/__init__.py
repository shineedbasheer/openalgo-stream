"""
Evermore WebSocket streaming module for OpenAlgo.

This module provides WebSocket integration with Evermore's MT Data Feed API,
following the OpenAlgo WebSocket proxy architecture.
"""

from .evermore_adapter import EvermoreWebSocketAdapter

__all__ = ["EvermoreWebSocketAdapter"]
