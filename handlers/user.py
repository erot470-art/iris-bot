from telebot.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

def register_user_handlers(bot):
    @bot.message_handler(commands=["start"])
    def start(message: Message):
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
            "/profile — мой профиль",
            reply_markup=keyboard
        )

    @bot.message_handler(commands=["help"])
    def help_command(message: Message):
        bot.reply_to(
            message,
            "📖 **Список команд:**\n\n"
            "👤 **Пользовательские:**\n"
            "/start — приветствие\n"
            "/profile — мой профиль\n"
            "/обнять @user — обнять участника\n"
            "/поцеловать @user — поцеловать\n\n"
            "🛡️ **Админские:**\n"
            "/мут @user 60м — заглушить\n"
            "/бан @user — заблокировать"
        )

    @bot.callback_query_handler(func=lambda call: True)
    def callback_handler(call):
        if call.data == "stats":
            bot.answer_callback_query(call.id, "📊 Статистика: пока пусто")
        elif call.data == "profile":
            bot.answer_callback_query(call.id, "👤 Ваш профиль в разработке")
