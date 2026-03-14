"""
Order placement logic for the Binance Futures Trading Bot.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from .client import BinanceClient, BinanceAPIError, BinanceNetworkError
from .logging_config import get_logger
from .validators import validate_order_params

logger = get_logger("orders")

# Client-side stop watcher defaults
STOP_POLL_INTERVAL = 2.0   # seconds between mark-price checks
STOP_MAX_WAIT      = 300   # seconds before giving up (5 minutes)


class OrderResult:
    """Structured representation of a placed order."""

    def __init__(self, raw: Dict[str, Any]) -> None:
        self.raw             = raw
        self.order_id        = raw.get("orderId")
        self.client_order_id = raw.get("clientOrderId")
        self.symbol          = raw.get("symbol")
        self.side            = raw.get("side")
        self.order_type      = raw.get("type")
        self.status          = raw.get("status")
        self.orig_qty        = raw.get("origQty")
        self.executed_qty    = raw.get("executedQty", "0")
        self.avg_price       = raw.get("avgPrice")
        self.price           = raw.get("price")
        self.stop_price      = raw.get("stopPrice")
        self.time_in_force   = raw.get("timeInForce")
        self.update_time     = raw.get("updateTime")

    def summary_lines(self) -> list[str]:
        lines = [
            f"  Order ID      : {self.order_id}",
            f"  Client OID    : {self.client_order_id}",
            f"  Symbol        : {self.symbol}",
            f"  Side          : {self.side}",
            f"  Type          : {self.order_type}",
            f"  Status        : {self.status}",
            f"  Orig Qty      : {self.orig_qty}",
            f"  Executed Qty  : {self.executed_qty}",
        ]
        if self.avg_price and self.avg_price != "0":
            lines.append(f"  Avg Price     : {self.avg_price}")
        if self.price and self.price != "0":
            lines.append(f"  Limit Price   : {self.price}")
        if self.stop_price and self.stop_price != "0":
            lines.append(f"  Stop Price    : {self.stop_price}")
        if self.time_in_force:
            lines.append(f"  Time-in-Force : {self.time_in_force}")
        return lines


def place_market_order(client: BinanceClient, symbol: str,
                       side: str, quantity: str) -> OrderResult:
    """Place a MARKET order."""
    params = validate_order_params(symbol, side, "MARKET", quantity)
    logger.info("Market order — symbol=%s side=%s qty=%s",
                params["symbol"], params["side"], params["quantity"])
    raw = client.place_order(
        symbol=params["symbol"], side=params["side"],
        type="MARKET", quantity=params["quantity"],
    )
    return OrderResult(raw)


def place_limit_order(client: BinanceClient, symbol: str, side: str,
                      quantity: str, price: str,
                      time_in_force: str = "GTC") -> OrderResult:
    """Place a LIMIT order."""
    params = validate_order_params(symbol, side, "LIMIT", quantity, price=price)
    logger.info("Limit order — symbol=%s side=%s qty=%s price=%s tif=%s",
                params["symbol"], params["side"], params["quantity"],
                params["price"], time_in_force)
    raw = client.place_order(
        symbol=params["symbol"], side=params["side"],
        type="LIMIT", quantity=params["quantity"],
        price=params["price"], timeInForce=time_in_force,
    )
    return OrderResult(raw)


def place_stop_limit_order(
    client: BinanceClient,
    symbol: str,
    side: str,
    quantity: str,
    price: str,
    stop_price: str,
    time_in_force: str = "GTC",
    poll_interval: float = STOP_POLL_INTERVAL,
    max_wait: float = STOP_MAX_WAIT,
) -> OrderResult:
    """
    Client-side Stop-Limit order for Binance Futures Testnet.

    The testnet does not support server-side STOP/STOP_MARKET order types
    (returns -4120 for all stop variants). This function implements the same
    behaviour client-side:

      1. Polls the mark price every `poll_interval` seconds.
      2. Triggers when: BUY  → mark price >= stop_price
                        SELL → mark price <= stop_price
      3. Places a real LIMIT order at `price` once triggered.

    Args:
        client:        Authenticated BinanceClient.
        symbol:        Trading pair, e.g. 'BTCUSDT'.
        side:          'BUY' or 'SELL'.
        quantity:      Order quantity.
        price:         Limit price for the order placed when stop fires.
        stop_price:    Trigger price.
                         BUY  — set ABOVE current mark price.
                         SELL — set BELOW current mark price.
        time_in_force: GTC / IOC / FOK (default: GTC).
        poll_interval: Seconds between mark-price polls (default: 2).
        max_wait:      Seconds before giving up (default: 300).

    Returns:
        OrderResult for the LIMIT order placed after the stop triggered.

    Raises:
        TimeoutError:        Stop never triggered within max_wait.
        KeyboardInterrupt:   User pressed Ctrl+C.
        BinanceAPIError:     API error on final LIMIT placement.
        BinanceNetworkError: Network failure during polling.
    """
    params = validate_order_params(
        symbol, side, "STOP_LIMIT", quantity, price=price, stop_price=stop_price
    )
    sym   = params["symbol"]
    _side = params["side"]
    qty   = params["quantity"]
    lmt   = params["price"]
    stop  = float(params["stop_price"])

    logger.info(
        "Stop-Limit (client watcher) — symbol=%s side=%s qty=%s "
        "limit=%s stop=%s tif=%s poll=%.1fs timeout=%ds",
        sym, _side, qty, lmt, stop, time_in_force, poll_interval, int(max_wait),
    )

    deadline = time.monotonic() + max_wait
    elapsed  = 0.0

    print(f"\n  ⏳  Watching {sym} mark price every {poll_interval}s")
    print(f"      Stop trigger : {stop:>12,.2f}")
    print(f"      Limit price  : {float(lmt):>12,.2f}")
    print(f"      Timeout      : {int(max_wait)}s  |  Press Ctrl+C to cancel\n")

    try:
        while True:
            mark = client.get_mark_price(sym)
            logger.debug("Poll — mark=%s stop=%s elapsed=%.0fs", mark, stop, elapsed)

            triggered = (
                (_side == "BUY"  and mark >= stop) or
                (_side == "SELL" and mark <= stop)
            )

            direction = "≥" if _side == "BUY" else "≤"
            print(f"  Mark: {mark:>12,.2f}  |  Stop: {stop:>12,.2f} ({direction})  "
                  f"|  Elapsed: {int(elapsed):>3}s", end="\r", flush=True)

            if triggered:
                print()  # newline after progress line
                logger.info("Stop triggered — mark=%.2f  placing LIMIT at %s", mark, lmt)
                print(f"\n  🎯  Stop triggered! Mark={mark:,.2f} "
                      f"{'≥' if _side == 'BUY' else '≤'} {stop:,.2f}")
                print(f"      Placing LIMIT {_side} {qty} @ {lmt} …\n")
                break

            if time.monotonic() >= deadline:
                print()
                msg = (f"Stop-limit timed out after {int(max_wait)}s — "
                       f"mark {mark:,.2f} never reached {stop:,.2f}.")
                logger.warning(msg)
                raise TimeoutError(msg)

            time.sleep(poll_interval)
            elapsed += poll_interval

    except KeyboardInterrupt:
        print("\n\n  ⚠️  Stop watcher cancelled by user.")
        logger.info("Stop watcher cancelled by user (Ctrl+C)")
        raise

    raw = client.place_order(
        symbol=sym, side=_side,
        type="LIMIT", quantity=qty,
        price=lmt, timeInForce=time_in_force,
    )
    logger.info("LIMIT order placed after stop trigger: %s", raw)
    return OrderResult(raw)
