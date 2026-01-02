A simple Telegram bot for tracking cryptocurrency prices using the CoinGecko API.
Supports on-demand price checks and periodic updates via subscriptions.

## Features
- Get current price of supported cryptocurrencies
- Show 24h price change
- Subscribe to regular price updates
- Unsubscribe at any time
- Persistent subscriptions stored in JSON
- Uses CoinGecko (no exchange accounts required)

## Supported coins
- BTC (Bitcoin)
- ETH (Ethereum)
- LTC (Litecoin)
- XRP (Ripple)
- SOL (Solana)
- DOGE (Dogecoin)
- ADA (Cardano)

## Commands
- `/start` — show help and available commands
- `/price BTC` — get current price of a coin
- `/subscribe BTC` — subscribe to regular updates
- `/unsubscribe BTC` — unsubscribe from updates

## How it works
- Prices are fetched from the CoinGecko public API
- Subscriptions are stored locally in `data.json`
- Every 10 minutes the bot sends updates to subscribed users
- Each chat can subscribe to multiple coins

## Tech stack
- Python 3
- python-telegram-bot
- requests
- python-dotenv
- CoinGecko API
