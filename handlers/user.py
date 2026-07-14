from telebot.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from bot.services.db import get_db

def register_user_handlers(bot):
    """Регистрирует пользовательские команды"""
    
    @bot.message_handler(commands=["start"])
    def start(message: Message):
        # Сохраняем пользователя в БД
        with get_db() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
                (message.from_user.id, message.from_user.username, message.from_user.first_name)
            )
            conn.commit()
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton("📊 Статистика", callback_data="stats"),
            InlineKeyboardButton("👤 Профиль", callback_data="profile")
        )
        
        bot.reply_to(
            message,
            "👋 Привет! Я — Iris, ваш чат-менеджер.\n"
            "Доступные команды:\n"
            "/start — приветствие\n"
            "/help — помощь\n"
            "/стата — моя статистика",
            reply_markup=keyboard
        )

    @bot.message_handler(commands=["help"])
    def help_command(message: Message):
        bot.reply_to(
            message,
            "📖 **Список команд:**\n\n"
            "👤 **Пользовательские:**\n"
            "/start — приветствие\n"
            "/help — помощь\n"
            "/обнять @user — обнять участника\n"
            "/поцеловать @user — поцеловать\n"
            "/кусь @user — укусить\n"
            "/стата — моя статистика\n\n"
            "🛡️ **Админские:**\n"
            "/мут @user 60м — заглушить\n"
            "/бан @user — заблокировать"
        )

    @bot.message_handler(commands=["стата"])
    def stats(message: Message):
        with get_db() as conn:
            user = conn.execute(
                "SELECT warns FROM users WHERE user_id = ?",
                (message.from_user.id,)
            ).fetchone()
            
            if user:
                bot.reply_to(message, f"📊 **Ваша статистика:**\n⚠️ Варнов: {user['warns']}")
            else:
                bot.reply_to(message, "📊 Вы ещё не зарегистрированы!")

    @bot.callback_query_handler(func=lambda call: True)
    def callback_handler(call):
        if call.data == "stats":
            bot.answer_callback_query(call.id, "📊 Статистика: пока пусто")
        elif call.data == "profile":
            bot.answer_callback_query(call.id, "👤 Ваш профиль в разработке")
