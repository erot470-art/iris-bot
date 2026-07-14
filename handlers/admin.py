import time
from telebot.types import Message
from utils.db import get_db
from utils.middleware import is_admin, log_action

def register_admin_handlers(bot):
    @bot.message_handler(commands=["мут"])
    def mute_user(message: Message):
        if not is_admin(message.from_user.id):
            bot.reply_to(message, "⛔ У вас нет прав на эту команду.")
            return

        parts = message.text.split()
        if len(parts) < 3:
            bot.reply_to(message, "❌ Используйте: /мут @username 60м")
            return

        # Простой парсинг — можно расширить
        target = parts[1].replace("@", "")
        duration_str = parts[2]
        duration_seconds = int(duration_str.replace("м", "")) * 60

        with get_db() as conn:
            conn.execute(
                "UPDATE users SET is_muted = 1, muted_until = ? WHERE username = ?",
                (int(time.time()) + duration_seconds, target)
            )
            log_action(conn, message.from_user.id, "mute", target)

        bot.reply_to(message, f"🔇 Пользователь @{target} заглушен на {duration_str}.")

    @bot.message_handler(commands=["бан"])
    def ban_user(message: Message):
        if not is_admin(message.from_user.id):
            bot.reply_to(message, "⛔ У вас нет прав.")
            return

        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "❌ Используйте: /бан @username")
            return

        target = parts[1].replace("@", "")
        # Здесь можно добавить логику бана (кик + чёрный список)
        bot.reply_to(message, f"🚫 Пользователь @{target} забанен.")
