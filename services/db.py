import sqlite3
from contextlib import contextmanager
from bot.config import DB_PATH

@contextmanager
def get_db():
    """Открывает соединение с БД и автоматически закрывает его"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row  # чтобы обращаться к колонкам по имени
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    """Создаёт таблицы в базе данных, если их нет"""
    # Создаём папку data/, если её нет
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    with get_db() as conn:
        # Таблица пользователей
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                warns INTEGER DEFAULT 0,
                is_muted INTEGER DEFAULT 0,
                muted_until INTEGER DEFAULT 0
            )
        """)
        
        # Таблица логов (история действий)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT,
                target_id INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
