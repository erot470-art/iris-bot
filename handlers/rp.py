import random
from telebot.types import Message

RP_ACTIONS = {
    "обнять": "🤗 {user} обнял(а) {target}!",
    "поцеловать": "😘 {user} поцеловал(а) {target}!",
    "кусь": "😈 {user} укусил(а) {target}!",
    "дать пять": "✋ {user} дал(а) пять {target}!",
}

def register_rp_handlers(bot):
    for action, template in RP_ACTIONS.items():
        @bot.message_handler(commands=[action])
        def rp_handler(message: Message, action=action, template=template):
            parts = message.text.split()
            if len(parts) < 2:
                bot.reply_to(message, f"❌ Используйте: /{action} @username")
                return

            target = parts[1].replace("@", "")
            user = message.from_user.first_name
            bot.reply_to(message, template.format(user=user, target=target))
