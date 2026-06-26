# Telegram-бот: по /join регистрирует игрока и шлёт клавиатуру управления.
# Нажатия на кнопки передаёт игровому серверу через API.
import requests
import telebot
from telebot import types

import config

TOKEN = config.get("TELEGRAM_BOT_TOKEN")
SERVER_URL = config.get("SERVER_URL", "http://127.0.0.1:8000")

# Текст кнопки -> направление для сервера
DIRECTIONS = {"⬆️": "up", "⬇️": "down", "⬅️": "left", "➡️": "right"}

bot = telebot.TeleBot(TOKEN)


def control_keyboard():
    """Клавиатура-стрелки для управления котом."""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(types.KeyboardButton("⬆️"))
    keyboard.row(
        types.KeyboardButton("⬅️"),
        types.KeyboardButton("⬇️"),
        types.KeyboardButton("➡️"),
    )
    return keyboard


def player_name(message):
    """Имя игрока — Telegram-никнейм (или имя, если ника нет)."""
    return message.from_user.username or message.from_user.first_name


@bot.message_handler(commands=["start"])
def handle_start(message):
    bot.send_message(message.chat.id, "Привет! Напиши /join, чтобы зайти в игру.")


@bot.message_handler(commands=["join"])
def handle_join(message):
    """Создаёт игрока на сервере и присылает клавиатуру управления."""
    name = player_name(message)
    try:
        requests.post(f"{SERVER_URL}/api/join", json={"name": name}, timeout=5)
    except requests.RequestException:
        bot.send_message(message.chat.id, "Игровой сервер недоступен.")
        return
    bot.send_message(
        message.chat.id,
        f"Ты в игре, {name}! Управляй котом стрелками.",
        reply_markup=control_keyboard(),
    )


@bot.message_handler(func=lambda m: m.text in DIRECTIONS)
def handle_move(message):
    """Передаёт направление движения кота на сервер."""
    name = player_name(message)
    direction = DIRECTIONS[message.text]
    try:
        response = requests.post(
            f"{SERVER_URL}/api/move",
            json={"name": name, "direction": direction},
            timeout=5,
        )
    except requests.RequestException:
        bot.send_message(message.chat.id, "Игровой сервер недоступен.")
        return

    # Игрока нет в игре (например, сервер перезапускали) — просим войти заново
    if response.status_code == 404:
        bot.send_message(message.chat.id, "Тебя нет в игре. Напиши /join.")


if __name__ == "__main__":
    bot.infinity_polling()
