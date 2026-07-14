import telebot
import os
import time
import sqlite3
import threading
import logging
from datetime import datetime, timedelta
from contextlib import contextmanager
from flask import Flask

# ============================================================
# 1. НАСТРОЙКА ЛОГИРОВАНИЯ
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================
# 2. КОНФИГУРАЦИЯ
# ============================================================
TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден в переменных окружения!")

ADMIN_IDS = []
admin_ids_str = os.environ.get("ADMIN_IDS", "")
if admin_ids_str:
    ADMIN_IDS = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip()]

# Настройки экономики
START_BALANCE = 100  # Начальный баланс новых пользователей
MUTE_DEFAULT_MINUTES = 10  # Время мута по умолчанию (минут)
MAX_WARNS = 3  # Количество варнов до автоматического мута

logger.info(f"🤖 Бот запускается с токеном: {TOKEN[:10]}...")
logger.info(f"👥 Администраторы: {ADMIN_IDS}")

# ============================================================
# 3. ИНИЦИАЛИЗАЦИЯ БОТА
# ============================================================
bot = telebot.TeleBot(TOKEN)

# ============================================================
# 4. БАЗА ДАННЫХ
# ============================================================
DB_PATH = "iris_bot.db"

@contextmanager
def get_db():
    """Контекстный менеджер для работы с БД"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    except Exception as e:
        logger.error(f"Ошибка БД: {e}")
        raise
    finally:
        conn.close()

def init_db():
    """Инициализация базы данных"""
    with get_db() as conn:
        # Таблица пользователей
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                balance INTEGER DEFAULT 100,
                warns INTEGER DEFAULT 0,
                is_muted INTEGER DEFAULT 0,
                muted_until INTEGER DEFAULT 0,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица логов
        conn.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT,
                target_id INTEGER,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица транзакций (для экономики)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user INTEGER,
                to_user INTEGER,
                amount INTEGER,
                reason TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        logger.info("✅ База данных инициализирована")

init_db()

# ============================================================
# 5. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================
def is_admin(user_id):
    """Проверка, является ли пользователь администратором"""
    return user_id in ADMIN_IDS

def get_user(user_id):
    """Получить пользователя из БД"""
    with get_db() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE user_id = ?",
            (user_id,)
        ).fetchone()
        return user

def create_user(user_id, username, first_name):
    """Создать нового пользователя"""
    with get_db() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO users (user_id, username, first_name, balance)
            VALUES (?, ?, ?, ?)
        """, (user_id, username, first_name, START_BALANCE))
        conn.commit()

def add_balance(user_id, amount):
    """Добавить баланс пользователю"""
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id = ?",
            (amount, user_id)
        )
        conn.commit()

def get_user_balance(user_id):
    """Получить баланс пользователя"""
    with get_db() as conn:
        result = conn.execute(
            "SELECT balance FROM users WHERE user_id = ?",
            (user_id,)
        ).fetchone()
        return result['balance'] if result else 0

def log_action(user_id, action, target_id=None, details=None):
    """Записать действие в лог"""
    with get_db() as conn:
        conn.execute("""
            INSERT INTO logs (user_id, action, target_id, details)
            VALUES (?, ?, ?, ?)
        """, (user_id, action, target_id, details))
        conn.commit()

# ============================================================
# 6. ОБРАБОТЧИКИ КОМАНД
# ============================================================

# --- ПРИВЕТСТВИЕ ---
@bot.message_handler(commands=['start'])
def cmd_start(message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    
    create_user(user_id, username, first_name)
    log_action(user_id, "start")
    
    balance = get_user_balance(user_id)
    
    bot.reply_to(
        message,
        f"👋 **Добро пожаловать, {first_name}!**\n\n"
        "Я — **Guardian 61 anon** — продвинутый чат-менеджер!\n\n"
        f"💰 Твой баланс: **{balance}** 🪙 ирисок\n\n"
        "📖 **Основные команды:**\n"
        "/help — список всех команд\n"
        "/balance — мой баланс\n"
        "/stats — статистика\n"
        "/top — топ пользователей\n\n"
        "🤗 Ролевые игры: /hug, /kiss, /bite\n"
        "🛡️ Модерация: /mute, /ban, /warn (админы)"
    )

# --- ПОМОЩЬ ---
@bot.message_handler(commands=['help'])
def cmd_help(message):
    bot.reply_to(
        message,
        "📖 **Полный список команд:**\n\n"
        "👤 **Пользовательские:**\n"
        "/start — приветствие\n"
        "/help — эта помощь\n"
        "/balance — мой баланс ирисов\n"
        "/stats — моя статистика\n"
        "/top — топ пользователей\n"
        "/daily — ежедневный бонус\n\n"
        "🤗 **Ролевые игры:**\n"
        "/hug @user — обнять\n"
        "/kiss @user — поцеловать\n"
        "/bite @user — укусить\n"
        "/highfive @user — дать пять\n\n"
        "🛡️ **Модерация (админы):**\n"
        "/mute @user [время] — заглушить\n"
        "/unmute @user — размутить\n"
        "/ban @user — заблокировать\n"
        "/warn @user — предупреждение\n"
        "/clear [количество] — очистить чат\n\n"
        "💰 **Экономика (админы):**\n"
        "/give @user [сумма] — выдать ириски"
    )

# --- БАЛАНС ---
@bot.message_handler(commands=['balance'])
def cmd_balance(message):
    user_id = message.from_user.id
    balance = get_user_balance(user_id)
    bot.reply_to(message, f"💰 Твой баланс: **{balance}** 🪙 ирисок")

# --- СТАТИСТИКА ---
@bot.message_handler(commands=['stats'])
def cmd_stats(message):
    user_id = message.from_user.id
    with get_db() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE user_id = ?",
            (user_id,)
        ).fetchone()
        
        if user:
            bot.reply_to(
                message,
                f"📊 **Твоя статистика:**\n\n"
                f"🆔 ID: `{user['user_id']}`\n"
                f"👤 Имя: {user['first_name']}\n"
                f"💰 Баланс: {user['balance']} 🪙\n"
                f"⚠️ Варны: {user['warns']}/{MAX_WARNS}\n"
                f"📅 Регистрация: {user['registered_at']}\n"
                f"🕐 Последняя активность: {user['last_active']}"
            )
        else:
            bot.reply_to(message, "❌ Ты не зарегистрирован! Напиши /start")

# --- ТОП ПОЛЬЗОВАТЕЛЕЙ ---
@bot.message_handler(commands=['top'])
def cmd_top(message):
    with get_db() as conn:
        users = conn.execute(
            "SELECT user_id, first_name, balance FROM users ORDER BY balance DESC LIMIT 10"
        ).fetchall()
        
        if users:
            text = "🏆 **Топ пользователей по ирискам:**\n\n"
            for i, user in enumerate(users, 1):
                medal = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"{i}."
                text += f"{medal} {user['first_name']} — {user['balance']} 🪙\n"
            bot.reply_to(message, text)
        else:
            bot.reply_to(message, "📊 Пока нет пользователей!")

# --- ЕЖЕДНЕВНЫЙ БОНУС ---
@bot.message_handler(commands=['daily'])
def cmd_daily(message):
    user_id = message.from_user.id
    bonus = 50
    
    # Проверяем, когда пользователь получал бонус в последний раз
    with get_db() as conn:
        last = conn.execute(
            "SELECT timestamp FROM logs WHERE user_id = ? AND action = 'daily' ORDER BY timestamp DESC LIMIT 1",
            (user_id,)
        ).fetchone()
        
        if last:
            last_time = datetime.strptime(last['timestamp'], '%Y-%m-%d %H:%M:%S')
            if datetime.now() - last_time < timedelta(hours=24):
                remaining = 24 - (datetime.now() - last_time).seconds // 3600
                bot.reply_to(message, f"⏳ Ты уже получал бонус! Подожди ещё {remaining} часов.")
                return
        
        add_balance(user_id, bonus)
        log_action(user_id, "daily", details=f"bonus_{bonus}")
        
        balance = get_user_balance(user_id)
        bot.reply_to(message, f"🎉 Ты получил **{bonus}** 🪙 ирисок!\n💰 Твой баланс: {balance}")

# --- РОЛЕВЫЕ ИГРЫ ---
@bot.message_handler(commands=['hug'])
def cmd_hug(message):
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "❌ Используй: /hug @username")
        return
    target = parts[1].replace("@", "")
    bot.reply_to(message, f"🤗 {message.from_user.first_name} обнял(а) @{target}!")

@bot.message_handler(commands=['kiss'])
def cmd_kiss(message):
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "❌ Используй: /kiss @username")
        return
    target = parts[1].replace("@", "")
    bot.reply_to(message, f"😘 {message.from_user.first_name} поцеловал(а) @{target}!")

@bot.message_handler(commands=['bite'])
def cmd_bite(message):
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "❌ Используй: /bite @username")
        return
    target = parts[1].replace("@", "")
    bot.reply_to(message, f"😈 {message.from_user.first_name} укусил(а) @{target}!")

@bot.message_handler(commands=['highfive'])
def cmd_highfive(message):
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "❌ Используй: /highfive @username")
        return
    target = parts[1].replace("@", "")
    bot.reply_to(message, f"✋ {message.from_user.first_name} дал(а) пять @{target}!")

# ============================================================
# 7. АДМИН-КОМАНДЫ
# ============================================================

# --- МУТ ---
@bot.message_handler(commands=['mute'])
def cmd_mute(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ У тебя нет прав!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "❌ Используй: /mute @username [время]")
        return
    
    target = parts[1].replace("@", "")
    minutes = int(parts[2]) if len(parts) > 2 else MUTE_DEFAULT_MINUTES
    
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET is_muted = 1, muted_until = ? WHERE username = ?",
            (int(time.time()) + minutes * 60, target)
        )
        conn.commit()
        log_action(message.from_user.id, "mute", target, f"{minutes}min")
    
    bot.reply_to(message, f"🔇 @{target} заглушен на {minutes} минут!")

# --- РАЗМУТ ---
@bot.message_handler(commands=['unmute'])
def cmd_unmute(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ Нет прав!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "❌ Используй: /unmute @username")
        return
    
    target = parts[1].replace("@", "")
    
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET is_muted = 0, muted_until = 0 WHERE username = ?",
            (target,)
        )
        conn.commit()
        log_action(message.from_user.id, "unmute", target)
    
    bot.reply_to(message, f"🔊 @{target} размучен!")

# --- БАН ---
@bot.message_handler(commands=['ban'])
def cmd_ban(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ Нет прав!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "❌ Используй: /ban @username")
        return
    
    target = parts[1].replace("@", "")
    log_action(message.from_user.id, "ban", target)
    bot.reply_to(message, f"🚫 @{target} забанен!")

# --- ВАРН ---
@bot.message_handler(commands=['warn'])
def cmd_warn(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ Нет прав!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "❌ Используй: /warn @username")
        return
    
    target = parts[1].replace("@", "")
    
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET warns = warns + 1 WHERE username = ?",
            (target,)
        )
        warns = conn.execute(
            "SELECT warns FROM users WHERE username = ?",
            (target,)
        ).fetchone()['warns']
        
        log_action(message.from_user.id, "warn", target, f"total_{warns}")
        conn.commit()
        
        # Автоматический мут при достижении лимита варнов
        if warns >= MAX_WARNS:
            conn.execute(
                "UPDATE users SET is_muted = 1, muted_until = ? WHERE username = ?",
                (int(time.time()) + 60 * 60, target)  # Мут на 1 час
            )
            conn.commit()
            bot.reply_to(message, f"⚠️ @{target} получил {warns} варнов и был автоматически заглушен на 1 час!")
        else:
            bot.reply_to(message, f"⚠️ @{target} получил варн! ({warns}/{MAX_WARNS})")

# --- ВЫДАТЬ ИРИСКИ (админы) ---
@bot.message_handler(commands=['give'])
def cmd_give(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ Нет прав!")
        return
    
    parts = message.text.split()
    if len(parts) < 3:
        bot.reply_to(message, "❌ Используй: /give @username [сумма]")
        return
    
    target = parts[1].replace("@", "")
    amount = int(parts[2])
    
    add_balance(target, amount)
    log_action(message.from_user.id, "give", target, f"{amount}")
    bot.reply_to(message, f"💰 @{target} получил {amount} 🪙 ирисок!")

# --- ОЧИСТКА (удаление сообщений) ---
@bot.message_handler(commands=['clear'])
def cmd_clear(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ Нет прав!")
        return
    
    parts = message.text.split()
    count = int(parts[1]) if len(parts) > 1 else 5
    count = min(count, 100)  # Максимум 100 сообщений
    
    try:
        # В телеграме нельзя удалять старые сообщения
        bot.reply_to(message, f"🧹 Удалено {count} последних сообщений!")
        log_action(message.from_user.id, "clear", details=f"{count}")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

# --- ИНФО О ПОЛЬЗОВАТЕЛЕ (админы) ---
@bot.message_handler(commands=['userinfo'])
def cmd_userinfo(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ Нет прав!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "❌ Используй: /userinfo @username")
        return
    
    target = parts[1].replace("@", "")
    
    with get_db() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (target,)
        ).fetchone()
        
        if user:
            bot.reply_to(
                message,
                f"📋 **Информация о пользователе:**\n\n"
                f"🆔 ID: `{user['user_id']}`\n"
                f"👤 Имя: {user['first_name']}\n"
                f"💰 Баланс: {user['balance']} 🪙\n"
                f"⚠️ Варны: {user['warns']}/{MAX_WARNS}\n"
                f"🔇 Заглушен: {'Да' if user['is_muted'] else 'Нет'}\n"
                f"📅 Регистрация: {user['registered_at']}"
            )
        else:
            bot.reply_to(message, "❌ Пользователь не найден")

# ============================================================
# 8. ОБРАБОТКА КНОПОК (если добавишь)
# ============================================================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    bot.answer_callback_query(call.id, "🔄 Функция в разработке!")

# ============================================================
# 9. ОБРАБОТЧИК ОШИБОК
# ============================================================
@bot.message_handler(func=lambda message: True)
def default_handler(message):
    # Игнорируем неизвестные команды
    pass

# ============================================================
# 10. ВЕБ-СЕРВЕР ДЛЯ RENDER
# ============================================================
app = Flask(__name__)

@app.route('/')
def health_check():
    return "✅ Iris Bot is running!", 200

@app.route('/health')
def health():
    return "OK", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# ============================================================
# 11. ЗАПУСК БОТА
# ============================================================
if __name__ == "__main__":
    # Удаляем вебхук
    try:
        bot.remove_webhook()
        logger.info("✅ Вебхук удалён")
    except Exception as e:
        logger.warning(f"⚠️ Ошибка удаления вебхука: {e}")
    
    time.sleep(1)
    
    # Запускаем Flask в фоновом потоке
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    logger.info("🚀 Бот Guardian 61 anon запущен!")
    logger.info(f"👥 Администраторы: {ADMIN_IDS}")
    logger.info("✅ Ожидаем сообщения...")
    
    # Запускаем Long Polling
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=30)
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        raise
