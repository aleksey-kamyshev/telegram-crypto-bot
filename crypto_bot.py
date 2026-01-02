import logging
import os
import json
from pathlib import Path

import requests
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# ---------- Настройка логов ----------
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ---------- Настройки и файлы ----------
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY")  # можно оставить пустым

if not TELEGRAM_TOKEN:
    raise RuntimeError("Не задан TELEGRAM_TOKEN в .env")

DATA_FILE = Path("data.json")

# Карта тикер -> CoinGecko ID
COINS = {
    "btc": "bitcoin",
    "eth": "ethereum",
    "ltc": "litecoin",
    "xrp": "ripple",
    "sol": "solana",
    "doge": "dogecoin",
    "ada": "cardano",
}

# ---------- Работа с файлом данных ----------
def load_data() -> dict:
    if not DATA_FILE.exists():
        return {"subscriptions": {}}
    try:
        with DATA_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        logger.warning("data.json битый, начинаю с чистого")
        return {"subscriptions": {}}


def save_data(data: dict) -> None:
    tmp = DATA_FILE.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(DATA_FILE)


# ---------- Работа с CoinGecko ----------
def fetch_prices(symbols: list[str]) -> dict:
    """
    symbols: ["btc", "eth"]
    Возвращает dict вида:
    {
      "BTC": {"price": 12345.67, "change": 1.23},
      ...
    }
    """
    # нормализация тикеров
    symbols_norm = []
    id_by_symbol = {}

    for s in symbols:
        s_low = s.lower()
        if s_low not in COINS:
            continue
        coin_id = COINS[s_low]
        symbols_norm.append(s_low)
        id_by_symbol[s_low.upper()] = coin_id

    if not symbols_norm:
        return {}

    ids_str = ",".join({cid for cid in id_by_symbol.values()})

    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": ids_str,
        "vs_currencies": "usd",
        "include_24hr_change": "true",
    }
    headers = {}
    if COINGECKO_API_KEY:
        headers["x-cg-demo-api-key"] = COINGECKO_API_KEY

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        logger.error("Ошибка при запросе к CoinGecko: %s", e)
        return {}

    data = resp.json()
    result: dict[str, dict] = {}

    for sym_upper, cid in id_by_symbol.items():
        coin_info = data.get(cid)
        if not coin_info:
            continue
        price = coin_info.get("usd")
        change = coin_info.get("usd_24h_change")
        result[sym_upper] = {"price": price, "change": change}

    return result


# ---------- Команды бота ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "Привет!\n\n"
        "Я крипто-бот.\n\n"
        "Команды:\n"
        "/price BTC — показать цену монеты\n"
        "/subscribe BTC — подписаться на регулярные обновления\n"
        "/unsubscribe BTC — отписаться\n\n"
        "Поддерживаемые монеты: " + ", ".join(sym.upper() for sym in COINS.keys())
    )
    await update.message.reply_text(text)


async def price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Использование: /price BTC")
        return

    symbol = context.args[0].lower()
    if symbol not in COINS:
        await update.message.reply_text(
            "Не знаю такую монету. Поддерживаю: "
            + ", ".join(sym.upper() for sym in COINS.keys())
        )
        return

    prices = fetch_prices([symbol])
    if not prices:
        await update.message.reply_text("Не удалось получить цену, попробуй позже.")
        return

    sym_up = symbol.upper()
    info = prices.get(sym_up)
    if not info or info["price"] is None:
        await update.message.reply_text("Цена недоступна.")
        return

    price_val = info["price"]
    change = info["change"]

    msg = f"{sym_up}: {price_val:.2f} USD"
    if change is not None:
        msg += f" ({change:+.2f}% за 24ч)"

    await update.message.reply_text(msg)


async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Использование: /subscribe BTC")
        return

    symbol = context.args[0].lower()
    if symbol not in COINS:
        await update.message.reply_text(
            "Не знаю такую монету. Поддерживаю: "
            + ", ".join(sym.upper() for sym in COINS.keys())
        )
        return

    chat_id = str(update.effective_chat.id)
    data = load_data()
    subs = data.setdefault("subscriptions", {})
    chat_subs = subs.get(chat_id, [])

    if symbol in chat_subs:
        await update.message.reply_text(f"Ты уже подписан на {symbol.upper()}.")
        return

    chat_subs.append(symbol)
    subs[chat_id] = chat_subs
    save_data(data)

    await update.message.reply_text(
        f"Ок, подписал на обновления по {symbol.upper()}."
    )


async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Использование: /unsubscribe BTC")
        return

    symbol = context.args[0].lower()
    chat_id = str(update.effective_chat.id)

    data = load_data()
    subs = data.setdefault("subscriptions", {})
    chat_subs = subs.get(chat_id, [])

    if symbol not in chat_subs:
        await update.message.reply_text(
            f"Ты и так не подписан на {symbol.upper()}."
        )
        return

    chat_subs.remove(symbol)
    subs[chat_id] = chat_subs
    save_data(data)

    await update.message.reply_text(f"Отписал от {symbol.upper()}.")


# ---------- Периодические обновления ----------
async def send_updates(context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    subs = data.get("subscriptions", {})

    for chat_id_str, symbols in subs.items():
        if not symbols:
            continue

        prices = fetch_prices(symbols)
        if not prices:
            continue

        lines = ["Обновление цен:"]
        for sym in sorted(prices.keys()):
            info = prices[sym]
            price_val = info["price"]
            change = info["change"]
            if price_val is None:
                continue

            line = f"{sym}: {price_val:.2f} USD"
            if change is not None:
                line += f" ({change:+.2f}% за 24ч)"
            lines.append(line)

        if len(lines) == 1:
            continue

        text = "\n".join(lines)

        try:
            await context.bot.send_message(chat_id=int(chat_id_str), text=text)
        except Exception as e:
            logger.error("Не смог отправить сообщение в чат %s: %s", chat_id_str, e)


# ---------- Точка входа ----------
def main() -> None:
    application = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("price", price))
    application.add_handler(CommandHandler("subscribe", subscribe))
    application.add_handler(CommandHandler("unsubscribe", unsubscribe))

    # каждые 10 минут
    job_queue = application.job_queue
    job_queue.run_repeating(send_updates, interval=600, first=10)

    application.run_polling()


if __name__ == "__main__":
    main()
