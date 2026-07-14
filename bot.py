import telebot
import os
import time
import sqlite3
from contextlib import contextmanager

# ===== КОНФИГ =====
TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден!")

ADMIN_IDS = []
admin_ids_str = os.environ.get("ADMIN_IDS", "")
if admin_ids_str:
    ADMIN_IDS = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip()]

bot = telebot.TeleBot(TOKEN)

# ===== БАЗА ДАННЫХ =====
@contextmanager
def get_db():
    conn = sqlite3.connect("iris_bot.db")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                warns INTEGER DEFAULT 0
            )
        """)
        conn.commit()
        print("✅ База данных инициализирована")

init_db()

def is_admin(user_id):
    return user_id in ADMIN_IDS

# ===== ПРИВЕТСТВИЕ =====
@bot.message_handler(commands=['start'])
def start(message):
    with get_db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
            (message.from_user.id, message.from_user.username, message.from_user.first_name)
        )
        conn.commit()
    
    bot.reply_to(
        message,
        "👋 **Привет! Я — Guardian 61 anon!**\n\n"
        "Я умею:\n"
        "🤗 Ролевые игры (обнять, поцеловать)\n"
        "🛡️ Модерировать чат (мут)\n\n"
        "Отправь /help для списка команд"
    )

@bot.message_handler(commands=['help'])
def help_command(message):
    bot.reply_to(
        message,
        "📖 **Команды:**\n\n"
        "/start — приветствие\n"
        "/help — помощь\n"
        "/обнять @user — обнять\n"
        "/поцеловать @user — поцеловать\n"
        "/кусь @user — укусить\n"
        "/мут @user 60м — заглушить (админ)\n"
        "/бан @user — заблокировать (админ)"
    )

# ===== РОЛЕВЫЕ ИГРЫ =====
@bot.message_handler(commands=['обнять'])
def hug(message):
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "❌ Используйте: /обнять @username")
        return
    target = parts[1].replace("@", "")
    bot.reply_to(message, f"🤗 {message.from_user.first_name} обнял(а) @{target}!")

@bot.message_handler(commands=['поцеловать'])
def kiss(message):
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "❌ Используйте: /поцеловать @username")
        return
    target = parts[1].replace("@", "")
    bot.reply_to(message, f"😘 {message.from_user.first_name} поцеловал(а) @{target}!")

@bot.message_handler(commands=['кусь'])
def bite(message):
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "❌ Используйте: /кусь @username")
        return
    target = parts[1].replace("@", "")
    bot.reply_to(message, f"😈 {message.from_user.first_name} укусил(а) @{target}!")

# ===== АДМИН-КОМАНДЫ =====
@bot.message_handler(commands=['мут'])
def mute_user(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ У вас нет прав на эту команду.")
        return

    parts = message.text.split()
    if len(parts) < 3:
        bot.reply_to(message, "❌ Используйте: /мут @username 60м")
        return

    target = parts[1].replace("@", "")
    duration = parts[2]
    bot.reply_to(message, f"🔇 Пользователь @{target} заглушен на {duration}.")

@bot.message_handler(commands=['бан'])
def ban_user(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ У вас нет прав.")
        return

    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "❌ Используйте: /бан @username")
        return

    target = parts[1].replace("@", "")
    bot.reply_to(message, f"🚫 Пользователь @{target} забанен.")

# ===== ЗАПУСК =====
print("🚀 Бот Guardian 61 anon запущен!")
print(f"👥 Админы: {ADMIN_IDS}")
bot.infinity_polling()import telebot
# ... (ваши остальные импорты)

# Ваша конфигурация, база данных и обработчики команд

# --- ДОБАВЬТЕ ЭТУ СТРОЧКУ ПЕРЕД ЗАПУСКОМ ---
# Удаляем активный вебхук, чтобы использовать Long Polling
bot.remove_webhook()
# -------------------------------------------

print("🚀 Бот Guardian 61 anon запущен!")
# ... (остальной код)
bot.infinity_polling()
bot.remove_webhook(
