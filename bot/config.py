import os
from pathlib import Path
from dotenv import load_dotenv

# Находим корневую папку проекта (там где .env)
# __file__ = путь к этому файлу
# .parent = подняться на уровень выше (из bot/ в iris-bot/)
BASE_DIR = Path(__file__).parent.parent

# Загружаем переменные из файла .env
load_dotenv(BASE_DIR / ".env")

# Читаем токен
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден в .env!")

# Читаем ID администраторов
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

# Путь к файлу базы данных
DB_PATH = BASE_DIR / "data" / "iris_bot.db"
