#!/usr/bin/env python3
"""
Iris Бот — Чат-менеджер на Python с Long Polling
Запуск: python bot.py
"""

import logging
import telebot
from config import BOT_TOKEN
from utils.db import init_db
from handlers.admin import register_admin_handlers
from handlers.user import register_user_handlers
from handlers.rp import register_rp_handlers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

def main():
    logger.info("🚀 Запуск Iris-бота в режиме Long Polling...")

    # Инициализация БД
    init_db()
    logger.info("📦 База данных инициализирована")

    # Создаём бота
    bot = telebot.TeleBot(BOT_TOKEN)

    # Регистрируем обработчики
    register_admin_handlers(bot)
    register_user_handlers(bot)
    register_rp_handlers(bot)

    # Запуск Long Polling
    logger.info("✅ Бот готов. Ожидаем сообщения...")
    bot.infinity_polling(timeout=60, long_polling_timeout=30)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
