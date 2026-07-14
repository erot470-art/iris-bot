import telebot
import os
import time
import sqlite3
import threading
from contextlib import contextmanager
from flask import Flask

# ===== КОНФИГУРАЦИЯ =====
TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден!")

ADMIN_IDS = []
admin_ids_str = os.environ.get("ADMIN_IDS", "")
if admin_ids_str:
    ADMIN_IDS = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip()]

print(f"🔑 Токен: {TOKEN[:10]}...")
print(f"👥 Админы: {ADMIN_IDS}")

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
    print("✅ База данных готова")

init_db()

def is_admin(user_id):
    return user_id in ADMIN_IDS

# ===== КОМАНДЫ =====
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
        "🤗 Ролевые игры: /обнять, /поцеловать, /кусь\n"
        "🛡️ Модерация: /мут, /бан (только админы)\n\n"
        "📖 Отправь /help для всех команд"
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
        "/стата — моя статистика\n"
        "/мут @user 60м — заглушить (админ)\n"
        "/бан @user — заблокировать (админ)\n"
        "/варн @user — предупреждение (админ)"
    )

@bot.message_handler(commands=['стата'])
def stats(message):
    with get_db() as conn:
        user = conn.execute(
            "SELECT warns FROM users WHERE user_id = ?",
            (message.from_user.id,)
        ).fetchone()
        
        if user:
            bot.reply_to(message, f"📊 **Ваша статистика:**\n⚠️ Варнов: {user['warns']}")
        else:
            bot.reply_to(message, "📊 Вы ещё не зарегистрированы!")

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
        bot.reply_to(message, "⛔ Нет прав!")
        return

    parts = message.text.split()
    if len(parts) < 3:
        bot.reply_to(message, "❌ Используйте: /мут @username 60м")
        return

    target = parts[1].replace("@", "")
    duration = parts[2]
    bot.reply_to(message, f"🔇 @{target} заглушен на {duration}.")

@bot.message_handler(commands=['бан'])
def ban_user(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ Нет прав!")
        return

    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "❌ Используйте: /бан @username")
        return

    target = parts[1].replace("@", "")
    bot.reply_to(message, f"🚫 @{target} забанен!")

@bot.message_handler(commands=['варн'])
def warn_user(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ Нет прав!")
        return

    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "❌ Используйте: /варн @username")
        return

    target = parts[1].replace("@", "")
    
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET warns = warns + 1 WHERE username = ?",
            (target,)
        )
        conn.commit()
    
    bot.reply_to(message, f"⚠️ @{target} получил предупреждение!")

# ===== ВЕБ-СЕРВЕР ДЛЯ RENDER =====
app = Flask(__name__)

@app.route('/')
def health_check():
    return "✅ Бот работает!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# ===== ЗАПУСК =====
# Удаляем вебхук, чтобы использовать Long Polling
bot.remove_webhook()

# Запускаем веб-сервер в фоновом потоке (для Render)
flask_thread = threading.Thread(target=run_flask)
flask_thread.daemon = True
flask_thread.start()

print("🚀 Бот Guardian 61 anon запущен!")
print(f"👥 Админы: {ADMIN_IDS}")
print("✅ Ожидаем сообщения...")

# Запускаем бота
bot.infinity_polling(timeout=60, long_polling_timeout=30)
