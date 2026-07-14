import logging
import telebot
import sys
from pathlib import Path

# Добавляем корневую папку в путь, чтобы Python видел все модули
sys.path.insert(0, str(Path(__file__).parent.parent))

# ===== ПРАВИЛЬНЫЕ ИМПОРТЫ =====
from bot.config import BOT_TOKEN, DB_PATH
from bot.services.db import init_db
from bot.handlers.admin import register_admin_handlers
from bot.handlers.user import register_user_handlers
from bot.handlers.rp import register_rp_handlers

# Настройка логирования (чтобы видеть, что происходит)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

def main():
    logger.info("🚀 Запуск Iris-бота в режиме Long Polling...")
    
    # Создаём папку для данных (база данных, логи)
    (Path(__file__).parent.parent / "data").mkdir(exist_ok=True)
    
    # Создаём таблицы в базе данных
    init_db()
    logger.info(f"📦 База данных: {DB_PATH}")
    
    # Создаём объект бота
    bot = telebot.TeleBot(BOT_TOKEN)
    
    # Подключаем все обработчики команд
    register_admin_handlers(bot)
    register_user_handlers(bot)
    register_rp_handlers(bot)
    
    logger.info("✅ Бот готов. Ожидаем сообщения...")
    
    # Запускаем бота (он будет работать постоянно)
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=30)
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    main()
