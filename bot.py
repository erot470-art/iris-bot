import telebot
import os
import time
import sqlite3
import threading
import logging
import random
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
    raise ValueError("❌ BOT_TOKEN не найден!")

ADMIN_IDS = []
admin_ids_str = os.environ.get("ADMIN_IDS", "")
if admin_ids_str:
    ADMIN_IDS = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip()]

# Настройки
START_BALANCE = 100
MAX_WARNS = 3
MUTE_DEFAULT_MINUTES = 10

bot = telebot.TeleBot(TOKEN)

# ============================================================
# 3. БАЗА ДАННЫХ (РАСШИРЕННАЯ)
# ============================================================
DB_PATH = "iris_bot.db"

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with get_db() as conn:
        # Пользователи
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                balance INTEGER DEFAULT 100,
                warns INTEGER DEFAULT 0,
                is_muted INTEGER DEFAULT 0,
                muted_until INTEGER DEFAULT 0,
                rank INTEGER DEFAULT 0,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Логи
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
        
        # Браки
        conn.execute("""
            CREATE TABLE IF NOT EXISTS marriages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user1 INTEGER,
                user2 INTEGER,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Репутация
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reputation (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                chat_id INTEGER,
                likes INTEGER DEFAULT 0,
                stars INTEGER DEFAULT 0,
                UNIQUE(user_id, chat_id)
            )
        """)
        
        # Баны
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                chat_id INTEGER,
                reason TEXT,
                banned_by INTEGER,
                until TIMESTAMP,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Транзакции
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
# 4. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================
def is_admin(user_id):
    """Проверка, является ли пользователь администратором"""
    return user_id in ADMIN_IDS

def has_rank(user_id, required_rank):
    """Проверка ранга пользователя"""
    with get_db() as conn:
        user = conn.execute(
            "SELECT rank FROM users WHERE user_id = ?",
            (user_id,)
        ).fetchone()
        if user:
            return user['rank'] >= required_rank
        return False

def get_user(user_id):
    with get_db() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE user_id = ?",
            (user_id,)
        ).fetchone()

def create_user(user_id, username, first_name):
    with get_db() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO users (user_id, username, first_name, balance)
            VALUES (?, ?, ?, ?)
        """, (user_id, username, first_name, START_BALANCE))
        conn.commit()

def get_balance(user_id):
    with get_db() as conn:
        result = conn.execute(
            "SELECT balance FROM users WHERE user_id = ?",
            (user_id,)
        ).fetchone()
        return result['balance'] if result else 0

def add_balance(user_id, amount):
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id = ?",
            (amount, user_id)
        )
        conn.commit()

def log_action(user_id, action, target_id=None, details=None):
    with get_db() as conn:
        conn.execute("""
            INSERT INTO logs (user_id, action, target_id, details)
            VALUES (?, ?, ?, ?)
        """, (user_id, action, target_id, details))
        conn.commit()

def add_warn(target_id, reason="Не указана"):
    """Добавить варн пользователю"""
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET warns = warns + 1 WHERE user_id = ?",
            (target_id,)
        )
        warns = conn.execute(
            "SELECT warns FROM users WHERE user_id = ?",
            (target_id,)
        ).fetchone()['warns']
        conn.commit()
        
        # Автоматический мут при достижении лимита
        if warns >= MAX_WARNS:
            conn.execute(
                "UPDATE users SET is_muted = 1, muted_until = ? WHERE user_id = ?",
                (int(time.time()) + 3600, target_id)
            )
            conn.commit()
        return warns

def get_marriage(user_id):
    """Проверить, состоит ли пользователь в браке"""
    with get_db() as conn:
        result = conn.execute("""
            SELECT * FROM marriages WHERE user1 = ? OR user2 = ?
        """, (user_id, user_id)).fetchone()
        return result

def get_reputation(user_id, chat_id):
    """Получить репутацию пользователя в чате"""
    with get_db() as conn:
        result = conn.execute("""
            SELECT likes, stars FROM reputation
            WHERE user_id = ? AND chat_id = ?
        """, (user_id, chat_id)).fetchone()
        return result if result else {'likes': 0, 'stars': 0}

def update_reputation(user_id, chat_id, likes=0, stars=0):
    with get_db() as conn:
        conn.execute("""
            INSERT INTO reputation (user_id, chat_id, likes, stars)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, chat_id) DO UPDATE SET
            likes = likes + ?, stars = stars + ?
        """, (user_id, chat_id, likes, stars, likes, stars))
        conn.commit()

def get_top_users(chat_id, limit=10):
    """Топ пользователей по балансу в чате"""
    with get_db() as conn:
        # Здесь нужна более сложная логика, упрощённо:
        return conn.execute("""
            SELECT user_id, first_name, balance FROM users
            ORDER BY balance DESC LIMIT ?
        """, (limit,)).fetchall()

# ============================================================
# 5. МОДЕРАЦИЯ (БАНЫ, ВАРНЫ, МУТ)
# ============================================================

@bot.message_handler(commands=['мут'])
def cmd_mute(message):
    if not is_admin(message.from_user.id):
        return bot.reply_to(message, "⛔ Нет прав!")
    
    parts = message.text.split()
    if len(parts) < 2:
        return bot.reply_to(message, "❌ Используй: /мут @username [время] [причина]")
    
    try:
        target_id = int(parts[1].replace("@", "")) if parts[1].replace("@", "").isdigit() else None
        if not target_id:
            # Попробуем найти по username
            username = parts[1].replace("@", "")
            with get_db() as conn:
                user = conn.execute(
                    "SELECT user_id FROM users WHERE username = ?",
                    (username,)
                ).fetchone()
                if user:
                    target_id = user['user_id']
                else:
                    return bot.reply_to(message, "❌ Пользователь не найден!")
        
        minutes = int(parts[2]) if len(parts) > 2 else MUTE_DEFAULT_MINUTES
        reason = " ".join(parts[3:]) if len(parts) > 3 else "Не указана"
        
        with get_db() as conn:
            conn.execute(
                "UPDATE users SET is_muted = 1, muted_until = ? WHERE user_id = ?",
                (int(time.time()) + minutes * 60, target_id)
            )
            conn.commit()
        
        log_action(message.from_user.id, "mute", target_id, f"{minutes}мин - {reason}")
        bot.reply_to(message, f"🔇 Пользователь заглушен на {minutes} минут!\nПричина: {reason}")
    except ValueError:
        bot.reply_to(message, "❌ Ошибка! Используй: /мут @username 60м")

@bot.message_handler(commands=['размут'])
def cmd_unmute(message):
    if not is_admin(message.from_user.id):
        return bot.reply_to(message, "⛔ Нет прав!")
    
    parts = message.text.split()
    if len(parts) < 2:
        return bot.reply_to(message, "❌ Используй: /размут @username")
    
    target_id = int(parts[1].replace("@", "")) if parts[1].replace("@", "").isdigit() else None
    if not target_id:
        username = parts[1].replace("@", "")
        with get_db() as conn:
            user = conn.execute(
                "SELECT user_id FROM users WHERE username = ?",
                (username,)
            ).fetchone()
            if user:
                target_id = user['user_id']
            else:
                return bot.reply_to(message, "❌ Пользователь не найден!")
    
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET is_muted = 0, muted_until = 0 WHERE user_id = ?",
            (target_id,)
        )
        conn.commit()
    
    log_action(message.from_user.id, "unmute", target_id)
    bot.reply_to(message, f"🔊 Пользователь размучен!")

@bot.message_handler(commands=['бан'])
def cmd_ban(message):
    if not is_admin(message.from_user.id):
        return bot.reply_to(message, "⛔ Нет прав!")
    
    parts = message.text.split()
    if len(parts) < 2:
        return bot.reply_to(message, "❌ Используй: /бан @username [время] [причина]")
    
    target = parts[1].replace("@", "")
    duration = parts[2] if len(parts) > 2 else "навсегда"
    reason = " ".join(parts[3:]) if len(parts) > 3 else "Не указана"
    
    try:
        target_id = int(target) if target.isdigit() else None
        if not target_id:
            with get_db() as conn:
                user = conn.execute(
                    "SELECT user_id FROM users WHERE username = ?",
                    (target,)
                ).fetchone()
                if user:
                    target_id = user['user_id']
                else:
                    return bot.reply_to(message, "❌ Пользователь не найден!")
        
        # Сохраняем в базу банов
        until = None
        if duration != "навсегда" and duration.endswith(('д', 'ч', 'м')):
            # Простой парсинг срока
            if duration.endswith('д'):
                days = int(duration[:-1])
                until = int(time.time()) + days * 86400
            elif duration.endswith('ч'):
                hours = int(duration[:-1])
                until = int(time.time()) + hours * 3600
            elif duration.endswith('м'):
                minutes = int(duration[:-1])
                until = int(time.time()) + minutes * 60
        
        with get_db() as conn:
            conn.execute("""
                INSERT INTO bans (user_id, chat_id, reason, banned_by, until)
                VALUES (?, ?, ?, ?, ?)
            """, (target_id, message.chat.id, reason, message.from_user.id, until))
            conn.commit()
        
        log_action(message.from_user.id, "ban", target_id, f"{duration} - {reason}")
        bot.reply_to(message, f"🚫 @{target} забанен!\nСрок: {duration}\nПричина: {reason}")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['варн'])
def cmd_warn(message):
    if not is_admin(message.from_user.id):
        return bot.reply_to(message, "⛔ Нет прав!")
    
    parts = message.text.split()
    if len(parts) < 2:
        return bot.reply_to(message, "❌ Используй: /варн @username [причина]")
    
    target = parts[1].replace("@", "")
    reason = " ".join(parts[2:]) if len(parts) > 2 else "Не указана"
    
    try:
        target_id = int(target) if target.isdigit() else None
        if not target_id:
            with get_db() as conn:
                user = conn.execute(
                    "SELECT user_id FROM users WHERE username = ?",
                    (target,)
                ).fetchone()
                if user:
                    target_id = user['user_id']
                else:
                    return bot.reply_to(message, "❌ Пользователь не найден!")
        
        warns = add_warn(target_id, reason)
        log_action(message.from_user.id, "warn", target_id, f"{warns}/{MAX_WARNS} - {reason}")
        
        if warns >= MAX_WARNS:
            bot.reply_to(message, f"⚠️ @{target} получил {warns} варнов и был автоматически заглушен!\nПричина: {reason}")
        else:
            bot.reply_to(message, f"⚠️ @{target} получил варн! ({warns}/{MAX_WARNS})\nПричина: {reason}")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['банлист'])
def cmd_banlist(message):
    if not is_admin(message.from_user.id):
        return bot.reply_to(message, "⛔ Нет прав!")
    
    with get_db() as conn:
        bans = conn.execute(
            "SELECT * FROM bans WHERE chat_id = ? ORDER BY timestamp DESC LIMIT 20",
            (message.chat.id,)
        ).fetchall()
        
        if bans:
            text = "🚫 **Список банов:**\n\n"
            for i, ban in enumerate(bans, 1):
                user = conn.execute(
                    "SELECT first_name FROM users WHERE user_id = ?",
                    (ban['user_id'],)
                ).fetchone()
                name = user['first_name'] if user else ban['user_id']
                until = "Навсегда" if not ban['until'] else datetime.fromtimestamp(ban['until']).strftime("%d.%m.%Y")
                text += f"{i}. {name} — {until}\n"
            bot.reply_to(message, text)
        else:
            bot.reply_to(message, "📊 Банов пока нет!")

# ============================================================
# 6. БРАКИ
# ============================================================

@bot.message_handler(commands=['брак'])
def cmd_marriage(message):
    user_id = message.from_user.id
    
    # Проверяем, не состоит ли уже в браке
    if get_marriage(user_id):
        return bot.reply_to(message, "💔 Ты уже в браке! Используй /развод для развода.")
    
    parts = message.text.split()
    if len(parts) < 2:
        return bot.reply_to(message, "❌ Используй: /брак @username")
    
    target = parts[1].replace("@", "")
    try:
        target_id = int(target) if target.isdigit() else None
        if not target_id:
            with get_db() as conn:
                user = conn.execute(
                    "SELECT user_id FROM users WHERE username = ?",
                    (target,)
                ).fetchone()
                if user:
                    target_id = user['user_id']
                else:
                    return bot.reply_to(message, "❌ Пользователь не найден!")
        
        if target_id == user_id:
            return bot.reply_to(message, "❌ Нельзя жениться на себе!")
        
        if get_marriage(target_id):
            return bot.reply_to(message, "💔 Этот пользователь уже в браке!")
        
        # Отправляем запрос
        keyboard = telebot.types.InlineKeyboardMarkup()
        keyboard.add(
            telebot.types.InlineKeyboardButton("💍 Да", callback_data=f"marry_yes_{user_id}_{target_id}"),
            telebot.types.InlineKeyboardButton("❌ Нет", callback_data=f"marry_no_{user_id}_{target_id}")
        )
        
        bot.send_message(
            target_id,
            f"💍 {message.from_user.first_name} предлагает тебе вступить в брак!",
            reply_markup=keyboard
        )
        
        bot.reply_to(message, "✅ Предложение отправлено! Ожидай ответа.")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['развод'])
def cmd_divorce(message):
    user_id = message.from_user.id
    marriage = get_marriage(user_id)
    
    if not marriage:
        return bot.reply_to(message, "💔 Ты не в браке!")
    
    with get_db() as conn:
        conn.execute(
            "DELETE FROM marriages WHERE id = ?",
            (marriage['id'],)
        )
        conn.commit()
    
    partner = marriage['user2'] if marriage['user1'] == user_id else marriage['user1']
    log_action(user_id, "divorce", partner)
    bot.reply_to(message, "💔 Брак расторгнут!")

@bot.message_handler(commands=['мой_брак'])
def cmd_my_marriage(message):
    user_id = message.from_user.id
    marriage = get_marriage(user_id)
    
    if not marriage:
        return bot.reply_to(message, "💔 Ты не в браке!")
    
    partner = marriage['user2'] if marriage['user1'] == user_id else marriage['user1']
    with get_db() as conn:
        user = conn.execute(
            "SELECT first_name FROM users WHERE user_id = ?",
            (partner,)
        ).fetchone()
        name = user['first_name'] if user else partner
    
    bot.reply_to(
        message,
        f"💍 **Твой брак:**\n\n"
        f"👤 Партнёр: {name}\n"
        f"📅 Дата: {marriage['date']}"
    )

@bot.message_handler(commands=['браки'])
def cmd_marriages(message):
    with get_db() as conn:
        marriages = conn.execute(
            "SELECT * FROM marriages ORDER BY date DESC LIMIT 10"
        ).fetchall()
        
        if marriages:
            text = "💍 **Список браков:**\n\n"
            for i, m in enumerate(marriages, 1):
                user1 = conn.execute(
                    "SELECT first_name FROM users WHERE user_id = ?",
                    (m['user1'],)
                ).fetchone()
                user2 = conn.execute(
                    "SELECT first_name FROM users WHERE user_id = ?",
                    (m['user2'],)
                ).fetchone()
                name1 = user1['first_name'] if user1 else m['user1']
                name2 = user2['first_name'] if user2 else m['user2']
                text += f"{i}. {name1} + {name2}\n"
            bot.reply_to(message, text)
        else:
            bot.reply_to(message, "💍 Браков пока нет!")

# ============================================================
# 7. РП-КОМАНДЫ
# ============================================================

RP_ACTIONS = {
    "обнять": "🤗",
    "поцеловать": "😘",
    "ударить": "👊",
    "дать_пять": "✋",
    "пожать_руку": "🤝",
    "укусить": "😈",
    "облизывать": "👅",
}

for action, emoji in RP_ACTIONS.items():
    @bot.message_handler(commands=[action])
    def rp_handler(message, action=action, emoji=emoji):
        parts = message.text.split()
        if len(parts) < 2:
            return bot.reply_to(message, f"❌ Используй: /{action} @username")
        
        target = parts[1].replace("@", "")
        user = message.from_user.first_name
        bot.reply_to(message, f"{emoji} {user} {action}(а) @{target}!")

# ============================================================
# 8. РЕПУТАЦИЯ И ТОПЫ
# ============================================================

@bot.message_handler(commands=['+'])
def cmd_like(message):
    """Лайкнуть сообщение"""
    if not message.reply_to_message:
        return bot.reply_to(message, "❌ Ответь на сообщение, которое хочешь лайкнуть!")
    
    user_id = message.reply_to_message.from_user.id
    chat_id = message.chat.id
    
    if user_id == message.from_user.id:
        return bot.reply_to(message, "❌ Нельзя лайкать себя!")
    
    update_reputation(user_id, chat_id, likes=1)
    bot.reply_to(message, f"👍 Плюс поставлен!")

@bot.message_handler(commands=['топ'])
def cmd_top(message):
    """Топ пользователей"""
    with get_db() as conn:
        users = conn.execute(
            "SELECT user_id, first_name, balance FROM users ORDER BY balance DESC LIMIT 10"
        ).fetchall()
        
        if users:
            text = "🏆 **Топ пользователей:**\n\n"
            for i, user in enumerate(users, 1):
                medal = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"{i}."
                text += f"{medal} {user['first_name']} — {user['balance']} 🪙\n"
            bot.reply_to(message, text)
        else:
            bot.reply_to(message, "📊 Нет данных!")

# ============================================================
# 9. ЭКОНОМИКА
# ============================================================

@bot.message_handler(commands=['баланс'])
def cmd_balance(message):
    user_id = message.from_user.id
    balance = get_balance(user_id)
    bot.reply_to(message, f"💰 Твой баланс: **{balance}** 🪙 ирисок")

@bot.message_handler(commands=['дать'])
def cmd_give(message):
    if not is_admin(message.from_user.id):
        return bot.reply_to(message, "⛔ Нет прав!")
    
    parts = message.text.split()
    if len(parts) < 3:
        return bot.reply_to(message, "❌ Используй: /дать @username [сумма]")
    
    target = parts[1].replace("@", "")
    amount = int(parts[2])
    
    try:
        target_id = int(target) if target.isdigit() else None
        if not target_id:
            with get_db() as conn:
                user = conn.execute(
                    "SELECT user_id FROM users WHERE username = ?",
                    (target,)
                ).fetchone()
                if user:
                    target_id = user['user_id']
                else:
                    return bot.reply_to(message, "❌ Пользователь не найден!")
        
        add_balance(target_id, amount)
        log_action(message.from_user.id, "give", target_id, f"{amount}")
        bot.reply_to(message, f"💰 @{target} получил {amount} 🪙 ирисок!")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

# ============================================================
# 10. УТИЛИТЫ
# ============================================================

@bot.message_handler(commands=['start'])
def cmd_start(message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    
    create_user(user_id, username, first_name)
    balance = get_balance(user_id)
    
    bot.reply_to(
        message,
        f"👋 **Добро пожаловать, {first_name}!**\n\n"
        "Я — **Guardian 61 anon** — продвинутый чат-менеджер!\n\n"
        f"💰 Твой баланс: **{balance}** 🪙\n\n"
        "📖 **Команды:**\n"
        "/help — список команд\n"
        "/баланс — мой баланс\n"
        "/топ — топ пользователей\n\n"
        "🤗 Ролевые игры: /обнять, /поцеловать, /ударить\n"
        "🛡️ Модерация: /мут, /бан, /варн (админы)\n"
        "💍 Отношения: /брак, /развод, /мой_брак"
    )

@bot.message_handler(commands=['help'])
def cmd_help(message):
    bot.reply_to(
        message,
        "📖 **Полный список команд:**\n\n"
        "👤 **Пользовательские:**\n"
        "/start — приветствие\n"
        "/help — помощь\n"
        "/баланс — мой баланс\n"
        "/топ — топ пользователей\n"
        "/мой_брак — информация о браке\n"
        "/браки — список браков\n\n"
        "🤗 **Ролевые игры:**\n"
        "/обнять @user\n"
        "/поцеловать @user\n"
        "/ударить @user\n"
        "/дать_пять @user\n\n"
        "🛡️ **Модерация (админы):**\n"
        "/мут @user [время] [причина]\n"
        "/размут @user\n"
        "/бан @user [время] [причина]\n"
        "/варн @user [причина]\n"
        "/банлист — список банов\n\n"
        "💍 **Отношения:**\n"
        "/брак @user — предложить брак\n"
        "/развод — расторгнуть брак\n"
        "/мой_брак — информация\n\n"
        "💰 **Экономика (админы):**\n"
        "/дать @user [сумма]"
    )

@bot.message_handler(commands=['ping'])
def cmd_ping(message):
    bot.reply_to(message, "🏓 Понг!")

# ============================================================
# 11. ОБРАБОТКА КНОПОК
# ============================================================

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data.startswith("marry_yes_"):
        _, _, user1, user2 = call.data.split("_")
        user1 = int(user1)
        user2 = int(user2)
        
        if call.from_user.id != user2:
            return bot.answer_callback_query(call.id, "❌ Это не для тебя!")
        
        if get_marriage(user1) or get_marriage(user2):
            return bot.answer_callback_query(call.id, "❌ Один из пользователей уже в браке!")
        
        with get_db() as conn:
            conn.execute(
                "INSERT INTO marriages (user1, user2) VALUES (?, ?)",
                (user1, user2)
            )
            conn.commit()
            log_action(user2, "marriage", user1)
        
        bot.answer_callback_query(call.id, "💍 Поздравляю с браком!")
        bot.edit_message_text("💍 Брак заключён!", call.message.chat.id, call.message.message_id)
        
        # Уведомляем первого
        bot.send_message(user1, f"💍 {call.from_user.first_name} согласился(ась) на брак!")
        
    elif call.data.startswith("marry_no_"):
        _, _, user1, user2 = call.data.split("_")
        user1 = int(user1)
        user2 = int(user2)
        
        if call.from_user.id != user2:
            return bot.answer_callback_query(call.id, "❌ Это не для тебя!")
        
        bot.answer_callback_query(call.id, "❌ Отказ!")
        bot.edit_message_text("❌ Предложение отклонено!", call.message.chat.id, call.message.message_id)
        bot.send_message(user1, f"❌ {call.from_user.first_name} отказался(ась) от брака!")

# ============================================================
# 12. ВЕБ-СЕРВЕР ДЛЯ RENDER
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
# 13. ЗАПУСК БОТА
# ============================================================

if __name__ == "__main__":
    # Удаляем вебхук
    try:
        bot.remove_webhook()
        logger.info("✅ Вебхук удалён")
    except Exception as e:
        logger.warning(f"⚠️ Ошибка удаления вебхука: {e}")
    
    time.sleep(1)
        # Регистрируем команды в Telegram
    try:
        commands = [
            telebot.types.BotCommand("start", "Главное меню и регистрация"),
            telebot.types.BotCommand("help", "Список всех команд"),
            telebot.types.BotCommand("баланс", "Мой баланс ирисок"),
            telebot.types.BotCommand("топ", "Топ пользователей"),
            telebot.types.BotCommand("брак", "Предложить брак @user"),
            telebot.types.BotCommand("развод", "Расторгнуть брак"),
            telebot.types.BotCommand("мой_брак", "Информация о браке"),
            telebot.types.BotCommand("браки", "Список браков в чате"),
            telebot.types.BotCommand("обнять", "Обнять @user"),
            telebot.types.BotCommand("поцеловать", "Поцеловать @user"),
            telebot.types.BotCommand("ударить", "Ударить @user"),
            telebot.types.BotCommand("дать_пять", "Дать пять @user"),
            telebot.types.BotCommand("пожать_руку", "Пожать руку @user"),
            telebot.types.BotCommand("мут", "Заглушить @user [время] (админ)"),
            telebot.types.BotCommand("бан", "Забанить @user [время] (админ)"),
            telebot.types.BotCommand("варн", "Выдать варн @user (админ)"),
            telebot.types.BotCommand("банлист", "Список банов (админ)"),
            telebot.types.BotCommand("дать", "Выдать ириски @user [сумма] (админ)"),
            telebot.types.BotCommand("ping", "Проверка работы бота"),
        ]
        bot.set_my_commands(commands)
        logger.info("✅ Команды зарегистрированы в Telegram")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось зарегистрировать команды: {e}")
    # Запускаем Flask
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    logger.info("🚀 Бот Guardian 61 anon запущен!")
    logger.info(f"👥 Администраторы: {ADMIN_IDS}")
    logger.info("✅ Ожидаем сообщения...")
    
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=30)
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        raise
