#!/usr/bin/env python3
"""
Binance Futures Testnet Trading Bot — CLI entry point.

Usage examples:
    python cli.py place-order --symbol BTCUSDT --side BUY --type MARKET --qty 0.001
    python cli.py place-order --symbol BTCUSDT --side SELL --type LIMIT --qty 0.001 --price 50000
    python cli.py place-order --symbol BTCUSDT --side BUY --type STOP_LIMIT \\
        --qty 0.001 --price 49000 --stop-price 49500
    python cli.py check-connection
    python cli.py account-info
"""

from __future__ import annotations

import argparse
import os
import sys
import textwrap
from typing import Optional

from dotenv import load_dotenv

from bot import (
    BinanceAPIError,
    BinanceClient,
    BinanceNetworkError,
    place_limit_order,
    place_market_order,
    place_stop_limit_order,
    setup_logging,
)

# ── Banner ────────────────────────────────────────────────────────────────────

BANNER = """\
╔══════════════════════════════════════════════════════╗
║   Binance Futures Testnet Trading Bot                ║
║   USDT-M Perpetual Futures                           ║
╚══════════════════════════════════════════════════════╝
"""

# ── Helpers ───────────────────────────────────────────────────────────────────


def _print_separator(char: str = "─", width: int = 54) -> None:
    print(char * width)


def _print_order_request(
    symbol: str,
    side: str,
    order_type: str,
    quantity: str,
    price: Optional[str],
    stop_price: Optional[str],
) -> None:
    _print_separator()
    print("  ORDER REQUEST SUMMARY")
    _print_separator()
    print(f"  Symbol      : {symbol.upper()}")
    print(f"  Side        : {side.upper()}")
    print(f"  Type        : {order_type.upper()}")
    print(f"  Quantity    : {quantity}")
    if price:
        print(f"  Price       : {price}")
    if stop_price:
        print(f"  Stop Price  : {stop_price}")
    _print_separator()


def _print_order_result(result) -> None:
    print("  ORDER RESPONSE DETAILS")
    _print_separator()
    for line in result.summary_lines():
        print(line)
    _print_separator()


def _load_credentials() -> tuple[str, str]:
    """Load API credentials from environment variables."""
    load_dotenv()
    api_key = os.getenv("BINANCE_API_KEY", "").strip()
    api_secret = os.getenv("BINANCE_API_SECRET", "").strip()
    if not api_key or not api_secret:
        print(
            "\n[ERROR] Missing API credentials.\n"
            "Set BINANCE_API_KEY and BINANCE_API_SECRET in a .env file or "
            "as environment variables.\n"
        )
        sys.exit(1)
    return api_key, api_secret


# ── Sub-command handlers ──────────────────────────────────────────────────────


def cmd_place_order(args: argparse.Namespace, client: BinanceClient, logger) -> int:
    """Handle the 'place-order' sub-command."""
    symbol = args.symbol.strip().upper()
    side = args.side.strip().upper()
    order_type = args.type.strip().upper()
    quantity = str(args.qty)
    price = str(args.price) if args.price is not None else None
    stop_price = str(args.stop_price) if args.stop_price is not None else None

    _print_order_request(symbol, side, order_type, quantity, price, stop_price)

    try:
        if order_type == "MARKET":
            result = place_market_order(client, symbol, side, quantity)
        elif order_type == "LIMIT":
            if price is None:
                print("[ERROR] --price is required for LIMIT orders.")
                return 1
            result = place_limit_order(client, symbol, side, quantity, price, args.tif)
        elif order_type == "STOP_LIMIT":
            if stop_price is None:
                print("[ERROR] --stop-price is required for STOP_LIMIT orders.")
                return 1
            if price is None:
                print("[ERROR] --price (limit price) is required for STOP_LIMIT orders.")
                return 1
            result = place_stop_limit_order(
                client, symbol, side, quantity, price, stop_price,
                args.tif,
            )
        else:
            print(f"[ERROR] Unsupported order type: {order_type}")
            return 1

    except KeyboardInterrupt:
        print("")
        return 1
    except ValueError as exc:
        logger.error("Validation error: %s", exc)
        print(f"\n[ERROR] Invalid input: {exc}\n")
        return 1
    except BinanceAPIError as exc:
        logger.error("Binance API error: code=%s msg=%s", exc.code, exc.msg)
        print(f"\n[ERROR] Binance API returned an error:\n  Code : {exc.code}\n  Msg  : {exc.msg}\n")
        return 1
    except TimeoutError as exc:
        logger.warning("Stop-limit timed out: %s", exc)
        print(f"\n[TIMEOUT] {exc}\n")
        return 1
    except KeyboardInterrupt:
        print("\n\n  ⚠️   Stop-limit watch cancelled by user.\n")
        return 1
    except BinanceNetworkError as exc:
        logger.error("Network error: %s", exc)
        print(f"\n[ERROR] Network failure: {exc}\n")
        return 1

    _print_order_result(result)
    print(f"\n  ✅  Order placed successfully! (orderId={result.order_id})\n")
    return 0


def cmd_check_connection(client: BinanceClient, logger) -> int:
    """Handle the 'check-connection' sub-command."""
    print("  Checking connection to Binance Futures Testnet …")
    try:
        data = client.get_server_time()
        print(f"\n  ✅  Connected! Server time (ms): {data.get('serverTime')}\n")
        return 0
    except BinanceNetworkError as exc:
        logger.error("Connection check failed: %s", exc)
        print(f"\n  ❌  Connection failed: {exc}\n")
        return 1
    except BinanceAPIError as exc:
        logger.error("Connection check API error: %s", exc)
        print(f"\n  ❌  API error: {exc}\n")
        return 1


def cmd_account_info(client: BinanceClient, logger) -> int:
    """Handle the 'account-info' sub-command."""
    print("  Fetching account information …")
    try:
        data = client.get_account()
        assets = [a for a in data.get("assets", []) if float(a.get("walletBalance", 0)) > 0]
        print("\n  ACCOUNT SUMMARY")
        _print_separator()
        print(f"  Total Wallet Balance (USDT) : {data.get('totalWalletBalance', 'N/A')}")
        print(f"  Available Balance (USDT)    : {data.get('availableBalance', 'N/A')}")
        print(f"  Total Unrealised PnL (USDT) : {data.get('totalUnrealizedProfit', 'N/A')}")
        if assets:
            print("\n  Non-zero Asset Balances:")
            for asset in assets:
                print(f"    {asset['asset']:10s}  wallet={asset['walletBalance']}  "
                      f"available={asset['availableBalance']}")
        _print_separator()
        print()
        return 0
    except BinanceAPIError as exc:
        logger.error("Account info API error: %s", exc)
        print(f"\n  ❌  API error: {exc}\n")
        return 1
    except BinanceNetworkError as exc:
        logger.error("Account info network error: %s", exc)
        print(f"\n  ❌  Network failure: {exc}\n")
        return 1


# ── Argument parser ───────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trading_bot",
        description=textwrap.dedent(
            """\
            Binance Futures Testnet Trading Bot
            Places MARKET, LIMIT, and STOP_LIMIT orders on USDT-M perpetual futures.
            """
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """\
            Examples:
              python cli.py check-connection
              python cli.py account-info
              python cli.py place-order --symbol BTCUSDT --side BUY --type MARKET --qty 0.001
              python cli.py place-order --symbol BTCUSDT --side SELL --type LIMIT \\
                  --qty 0.001 --price 50000
              python cli.py place-order --symbol BTCUSDT --side BUY --type STOP_LIMIT \\
                  --qty 0.001 --price 49000 --stop-price 49500
            """
        ),
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Console log verbosity (default: INFO).",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # ── check-connection ──────────────────────────────────────────────────────
    subparsers.add_parser(
        "check-connection",
        help="Verify connectivity to Binance Futures Testnet.",
    )

    # ── account-info ──────────────────────────────────────────────────────────
    subparsers.add_parser(
        "account-info",
        help="Display current testnet account balances.",
    )

    # ── place-order ───────────────────────────────────────────────────────────
    po = subparsers.add_parser(
        "place-order",
        help="Place a new futures order.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    po.add_argument(
        "--symbol", required=True, metavar="SYMBOL",
        help="Trading pair, e.g. BTCUSDT.",
    )
    po.add_argument(
        "--side", required=True, choices=["BUY", "SELL"],
        type=str.upper, help="Order side: BUY or SELL.",
    )
    po.add_argument(
        "--type", required=True,
        choices=["MARKET", "LIMIT", "STOP_LIMIT"],
        type=str.upper, dest="type",
        help="Order type.",
    )
    po.add_argument(
        "--qty", required=True, type=float,
        metavar="QUANTITY", help="Order quantity (base asset).",
    )
    po.add_argument(
        "--price", type=float, default=None,
        metavar="PRICE", help="Limit price (required for LIMIT / STOP_LIMIT).",
    )
    po.add_argument(
        "--stop-price", type=float, default=None,
        metavar="STOP_PRICE", dest="stop_price",
        help="Stop trigger price (required for STOP_LIMIT).",
    )
    po.add_argument(
        "--tif", default="GTC",
        choices=["GTC", "IOC", "FOK"],
        help="Time-in-force for LIMIT orders (default: GTC).",
    )
    po.add_argument(
        "--timeout", type=int, default=300,
        metavar="SECONDS",
        help="Max seconds to wait for a STOP_LIMIT to trigger (default: 300).",
    )

    return parser


# ── Entry point ───────────────────────────────────────────────────────────────


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    # Bootstrap logging before anything else
    logger = setup_logging(args.log_level)

    print(BANNER)

    api_key, api_secret = _load_credentials()
    client = BinanceClient(api_key=api_key, api_secret=api_secret)

    if args.command == "check-connection":
        return cmd_check_connection(client, logger)
    elif args.command == "account-info":
        return cmd_account_info(client, logger)
    elif args.command == "place-order":
        return cmd_place_order(args, client, logger)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
