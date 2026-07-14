from telebot.types import Message
from bot.services.db import get_db

RP_ACTIONS = {
    "обнять": "🤗 {user} обнял(а) {target}!",
    "поцеловать": "😘 {user} поцеловал(а) {target}!",
    "кусь": "😈 {user} укусил(а) {target}!",
    "дать пять": "✋ {user} дал(а) пять {target}!",
}

def register_rp_handlers(bot):
    """Регистрирует команды для ролевых игр"""
    
    for action, template in RP_ACTIONS.items():
        @bot.message_handler(commands=[action])
        def rp_handler(message: Message, action=action, template=template):
            parts = message.text.split()
            if len(parts) < 2:
                bot.reply_to(message, f"❌ Используйте: /{action} @username")
                return

            target = parts[1].replace("@", "")
            user = message.from_user.first_name
            
            # Сохраняем пользователя в БД
            with get_db() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
                    (message.from_user.id, message.from_user.username, user)
                )
                conn.commit()
            
            bot.reply_to(message, template.format(user=user, target=target))
