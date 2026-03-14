# Binance Futures Testnet Trading Bot

A clean, structured Python CLI application for placing orders on the **Binance Futures Testnet** (USDT-M Perpetual).

Supports **MARKET**, **LIMIT**, and **STOP_LIMIT** orders with proper logging, input validation, and error handling.

---

## Project Structure

```
trading_bot/
├── bot/
│   ├── __init__.py          # Package exports
│   ├── client.py            # Binance REST client (auth, signing, HTTP)
│   ├── orders.py            # Order placement logic + OrderResult model
│   ├── validators.py        # Input validation (raises ValueError on bad input)
│   └── logging_config.py   # Structured file + console logging setup
├── cli.py                   # CLI entry point (argparse)
├── logs/
│   └── trading_bot.log      # Auto-created on first run
├── .env.example             # Template for API credentials
├── requirements.txt
└── README.md
```

---

## Setup

### 1. Get Testnet API Credentials

1. Visit [https://testnet.binancefuture.com](https://testnet.binancefuture.com)
2. Log in (GitHub OAuth supported)
3. Go to **API Key** section and generate a key pair
4. Copy your **API Key** and **Secret Key**

### 2. Clone / Download the Project

```bash
git clone <repo-url>
cd trading_bot
```

### 3. Create a Virtual Environment (recommended)

```bash
python -m venv venv
source venv/bin/activate        # Linux / macOS
venv\Scripts\activate           # Windows
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure Credentials

```bash
cp .env.example .env
```

Edit `.env`:

```env
BINANCE_API_KEY=your_testnet_api_key_here
BINANCE_API_SECRET=your_testnet_api_secret_here
```

> **Note:** The `.env` file is never committed to source control. Keep your secrets safe.

---

## How to Run

### Verify Connectivity

```bash
python cli.py check-connection
```

Expected output:
```
  Checking connection to Binance Futures Testnet …
  ✅  Connected! Server time (ms): 1736932323000
```

---

### View Account Balances

```bash
python cli.py account-info
```

---

### Place a MARKET Order

```bash
# Buy 0.001 BTC at market price
python cli.py place-order --symbol BTCUSDT --side BUY --type MARKET --qty 0.001

# Sell 0.001 BTC at market price
python cli.py place-order --symbol BTCUSDT --side SELL --type MARKET --qty 0.001
```

---

### Place a LIMIT Order

```bash
# Sell 0.001 BTC at $45,000 (Good Till Cancelled)
python cli.py place-order --symbol BTCUSDT --side SELL --type LIMIT --qty 0.001 --price 45000

# Buy 0.5 ETH at $2,400 with Immediate-or-Cancel
python cli.py place-order --symbol ETHUSDT --side BUY --type LIMIT --qty 0.5 --price 2400 --tif IOC
```

---

### Place a STOP_LIMIT Order (Bonus Feature)

```bash
# Buy 0.001 BTC if price hits $49,500, with a limit of $49,000
python cli.py place-order \
  --symbol BTCUSDT \
  --side BUY \
  --type STOP_LIMIT \
  --qty 0.001 \
  --price 49000 \
  --stop-price 49500
```

---

### CLI Reference

```
usage: trading_bot [-h] [--log-level {DEBUG,INFO,WARNING,ERROR}]
                   {check-connection,account-info,place-order} ...

Sub-commands:
  check-connection   Verify connectivity to Binance Futures Testnet.
  account-info       Display current testnet account balances.
  place-order        Place a new futures order.

place-order arguments:
  --symbol SYMBOL         Trading pair, e.g. BTCUSDT  [required]
  --side {BUY,SELL}       Order side                  [required]
  --type {MARKET,LIMIT,STOP_LIMIT}  Order type        [required]
  --qty QUANTITY          Order quantity (base asset)  [required]
  --price PRICE           Limit price (LIMIT / STOP_LIMIT)
  --stop-price STOP_PRICE Stop trigger price (STOP_LIMIT)
  --tif {GTC,IOC,FOK}     Time-in-force (default: GTC)
  --log-level LEVEL       Console verbosity (default: INFO)
```

---

## Sample Output

```
╔══════════════════════════════════════════════════════╗
║   Binance Futures Testnet Trading Bot                ║
║   USDT-M Perpetual Futures                           ║
╚══════════════════════════════════════════════════════╝

──────────────────────────────────────────────────────
  ORDER REQUEST SUMMARY
──────────────────────────────────────────────────────
  Symbol      : BTCUSDT
  Side        : BUY
  Type        : MARKET
  Quantity    : 0.001
──────────────────────────────────────────────────────
  ORDER RESPONSE DETAILS
──────────────────────────────────────────────────────
  Order ID      : 4611686022722754180
  Client OID    : x-Cb7ytekJb4m4JFVzPOyE
  Symbol        : BTCUSDT
  Side          : BUY
  Type          : MARKET
  Status        : FILLED
  Orig Qty      : 0.001
  Executed Qty  : 0.001
  Avg Price     : 43721.80000
──────────────────────────────────────────────────────

  ✅  Order placed successfully! (orderId=4611686022722754180)
```

---

## Logging

All activity is written to `logs/trading_bot.log`:

- **DEBUG** — raw HTTP requests/responses (params + JSON body)
- **INFO**  — order intent and API responses  
- **ERROR** — validation failures, API errors, network issues

Logs rotate automatically at 5 MB (3 backups kept).

To see debug-level output on the console:

```bash
python cli.py --log-level DEBUG place-order --symbol BTCUSDT --side BUY --type MARKET --qty 0.001
```

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| Missing/invalid `--price` for LIMIT | Prints clear error, exits with code 1 |
| Invalid symbol / negative qty | `ValueError` caught, user-friendly message |
| Binance API error (e.g. -2019) | `BinanceAPIError` caught, shows code + message |
| Network timeout / DNS failure | `BinanceNetworkError` caught, explains failure |
| Missing API credentials | Exits immediately with setup instructions |

---

## Assumptions

- All trades are on **USDT-M Perpetual Futures** (not Spot or COIN-M).
- The bot uses the **one-way position mode** (default on testnet). If your account uses hedge mode, pass `positionSide` explicitly.
- Quantity precision must match the symbol's filters on Binance. If you receive a `-1111` (invalid precision) error, adjust your `--qty` to the correct decimal places for that symbol (e.g., BTCUSDT uses 3 decimals).
- The testnet is occasionally reset by Binance; if you see auth errors, regenerate your keys.
- No real money is involved — this bot targets the **testnet only**.

---

## Requirements

- Python **3.9+**
- `requests >= 2.31.0`
- `python-dotenv >= 1.0.0`

---

## License

MIT — free to use, modify, and distribute.
