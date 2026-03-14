"""
Input validation for the Binance Futures Trading Bot.
All validation functions raise ValueError with a descriptive message on failure.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Optional

VALID_SIDES = {"BUY", "SELL"}
VALID_ORDER_TYPES = {"MARKET", "LIMIT", "STOP_LIMIT"}

# Binance futures symbol conventions
SYMBOL_MIN_LEN = 5
SYMBOL_MAX_LEN = 20


def validate_symbol(symbol: str) -> str:
    """Validate and normalise a trading symbol (e.g. 'btcusdt' -> 'BTCUSDT')."""
    if not symbol or not isinstance(symbol, str):
        raise ValueError("Symbol must be a non-empty string.")
    cleaned = symbol.strip().upper()
    if not cleaned.isalnum():
        raise ValueError(f"Symbol '{cleaned}' must contain only letters and digits.")
    if not (SYMBOL_MIN_LEN <= len(cleaned) <= SYMBOL_MAX_LEN):
        raise ValueError(
            f"Symbol '{cleaned}' length {len(cleaned)} is outside the expected "
            f"range [{SYMBOL_MIN_LEN}, {SYMBOL_MAX_LEN}]."
        )
    return cleaned


def validate_side(side: str) -> str:
    """Validate order side and return uppercase version."""
    if not side or not isinstance(side, str):
        raise ValueError("Side must be a non-empty string.")
    cleaned = side.strip().upper()
    if cleaned not in VALID_SIDES:
        raise ValueError(
            f"Invalid side '{cleaned}'. Must be one of: {', '.join(sorted(VALID_SIDES))}."
        )
    return cleaned


def validate_order_type(order_type: str) -> str:
    """Validate order type and return uppercase version."""
    if not order_type or not isinstance(order_type, str):
        raise ValueError("Order type must be a non-empty string.")
    cleaned = order_type.strip().upper()
    if cleaned not in VALID_ORDER_TYPES:
        raise ValueError(
            f"Invalid order type '{cleaned}'. Must be one of: "
            f"{', '.join(sorted(VALID_ORDER_TYPES))}."
        )
    return cleaned


def validate_quantity(quantity: str | float | int) -> str:
    """
    Validate that quantity is a positive number.
    Returns the value as a plain string suitable for the Binance API.
    """
    try:
        qty = Decimal(str(quantity))
    except InvalidOperation:
        raise ValueError(f"Quantity '{quantity}' is not a valid number.")
    if qty <= 0:
        raise ValueError(f"Quantity must be positive, got {qty}.")
    return str(qty)


def validate_price(price: str | float | int | None, *, required: bool = False) -> Optional[str]:
    """
    Validate that price is a positive number.
    If *required* is True and price is None/empty, raise ValueError.
    Returns the value as a plain string suitable for the Binance API, or None.
    """
    if price is None or (isinstance(price, str) and not price.strip()):
        if required:
            raise ValueError("Price is required for LIMIT and STOP_LIMIT orders.")
        return None
    try:
        p = Decimal(str(price))
    except InvalidOperation:
        raise ValueError(f"Price '{price}' is not a valid number.")
    if p <= 0:
        raise ValueError(f"Price must be positive, got {p}.")
    return str(p)


def validate_stop_price(
    stop_price: str | float | int | None, *, required: bool = False
) -> Optional[str]:
    """Validate stop price for STOP_LIMIT orders (delegates to validate_price)."""
    try:
        return validate_price(stop_price, required=required)
    except ValueError as exc:
        raise ValueError(str(exc).replace("Price", "Stop price")) from exc


def validate_order_params(
    symbol: str,
    side: str,
    order_type: str,
    quantity: str | float | int,
    price: Optional[str | float | int] = None,
    stop_price: Optional[str | float | int] = None,
) -> dict:
    """
    Run all validations and return a cleaned parameter dict.
    Raises ValueError for any invalid field.
    """
    cleaned_type = validate_order_type(order_type)
    is_limit = cleaned_type in ("LIMIT", "STOP_LIMIT")

    return {
        "symbol": validate_symbol(symbol),
        "side": validate_side(side),
        "order_type": cleaned_type,
        "quantity": validate_quantity(quantity),
        "price": validate_price(price, required=is_limit),
        "stop_price": validate_stop_price(
            stop_price, required=(cleaned_type == "STOP_LIMIT")
        ),
    }
