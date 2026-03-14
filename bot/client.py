"""
Binance Futures Testnet REST client.
Handles authentication (HMAC-SHA256), request signing, and raw HTTP calls.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests

from .logging_config import get_logger

logger = get_logger("client")

TESTNET_BASE_URL = "https://testnet.binancefuture.com"
REQUEST_TIMEOUT = 10


class BinanceAPIError(Exception):
    def __init__(self, code: int, msg: str) -> None:
        self.code = code
        self.msg = msg
        super().__init__(f"Binance API error {code}: {msg}")


class BinanceNetworkError(Exception):
    pass


class BinanceClient:
    """
    Thin wrapper around the Binance Futures Testnet REST API.
    Automatically syncs to server time on first signed request to avoid -1021.
    """

    def __init__(self, api_key: str, api_secret: str,
                 base_url: str = TESTNET_BASE_URL) -> None:
        if not api_key or not api_secret:
            raise ValueError("Both api_key and api_secret must be provided.")
        self._api_key = api_key
        self._api_secret = api_secret
        self._base_url = base_url.rstrip("/")
        self._time_offset_ms: Optional[int] = None   # synced lazily
        self._session = requests.Session()
        self._session.headers.update({
            "X-MBX-APIKEY": self._api_key,
            "Content-Type": "application/x-www-form-urlencoded",
        })
        logger.info("BinanceClient initialised — base URL: %s", self._base_url)

    # ── Time sync ─────────────────────────────────────────────────────────────

    def _sync_time(self) -> None:
        """Fetch server time once and compute the local→server offset."""
        data = self._request("GET", "/fapi/v1/time", signed=False)
        server_ms = data["serverTime"]
        local_ms  = int(time.time() * 1000)
        self._time_offset_ms = server_ms - local_ms
        logger.debug("Time sync: server=%d local=%d offset=%+d ms",
                     server_ms, local_ms, self._time_offset_ms)

    def _timestamp_ms(self) -> int:
        if self._time_offset_ms is None:
            self._sync_time()
        return int(time.time() * 1000) + self._time_offset_ms

    # ── Auth ──────────────────────────────────────────────────────────────────

    def _sign(self, params: Dict[str, Any]) -> Dict[str, Any]:
        params["timestamp"] = self._timestamp_ms()
        query_string = urlencode(params)
        signature = hmac.new(
            self._api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        params["signature"] = signature
        return params

    # ── Core request ──────────────────────────────────────────────────────────

    def _request(self, method: str, path: str,
                 params: Optional[Dict[str, Any]] = None,
                 signed: bool = False) -> Any:
        params = params or {}
        if signed:
            params = self._sign(params)

        url = f"{self._base_url}{path}"
        log_params = {k: v for k, v in params.items() if k != "signature"}
        logger.debug("→ %s %s  params=%s", method.upper(), path, log_params)

        try:
            if method.upper() in ("GET", "DELETE"):
                response = self._session.request(
                    method, url, params=params, timeout=REQUEST_TIMEOUT)
            else:
                response = self._session.request(
                    method, url, data=params, timeout=REQUEST_TIMEOUT)
        except requests.exceptions.Timeout as exc:
            logger.error("Request timed out: %s %s", method, url)
            raise BinanceNetworkError(f"Request timed out: {exc}") from exc
        except requests.exceptions.ConnectionError as exc:
            logger.error("Connection error: %s", exc)
            raise BinanceNetworkError(f"Connection error: {exc}") from exc
        except requests.exceptions.RequestException as exc:
            logger.error("Unexpected request error: %s", exc)
            raise BinanceNetworkError(f"Request failed: {exc}") from exc

        logger.debug("← HTTP %s  body=%s", response.status_code, response.text[:500])

        try:
            data = response.json()
        except ValueError:
            raise BinanceNetworkError(
                f"Non-JSON response (HTTP {response.status_code}).")

        if isinstance(data, dict) and "code" in data and data["code"] != 200:
            raise BinanceAPIError(code=data["code"], msg=data.get("msg", "Unknown"))

        return data

    # ── Public API ────────────────────────────────────────────────────────────

    def get_server_time(self) -> Dict[str, Any]:
        return self._request("GET", "/fapi/v1/time")

    def get_exchange_info(self) -> Dict[str, Any]:
        return self._request("GET", "/fapi/v1/exchangeInfo")

    def get_account(self) -> Dict[str, Any]:
        return self._request("GET", "/fapi/v2/account", signed=True)

    def get_mark_price(self, symbol: str) -> float:
        """Return the current mark price for a symbol."""
        data = self._request("GET", "/fapi/v1/premiumIndex",
                             params={"symbol": symbol.upper()})
        return float(data["markPrice"])

    def place_order(self, **kwargs: Any) -> Dict[str, Any]:
        params = {k: v for k, v in kwargs.items() if v is not None}
        logger.info("Placing order: %s", params)
        result = self._request("POST", "/fapi/v1/order", params=params, signed=True)
        logger.info("Order response: %s", result)
        return result

    def get_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        return self._request("GET", "/fapi/v1/order",
                             params={"symbol": symbol, "orderId": order_id},
                             signed=True)

    def cancel_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        return self._request("DELETE", "/fapi/v1/order",
                             params={"symbol": symbol, "orderId": order_id},
                             signed=True)
