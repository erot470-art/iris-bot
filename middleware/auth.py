from bot.config import ADMIN_IDS

def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором"""
    return user_id in ADMIN_IDS

def log_action(conn, user_id: int, action: str, target_id: int = None):
    """Записывает действие в лог"""
    conn.execute(
        "INSERT INTO logs (user_id, action, target_id) VALUES (?, ?, ?)",
        (user_id, action, target_id)
    )
    conn.commit()
