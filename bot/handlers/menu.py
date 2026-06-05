from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.db.repository import ensure_user, log_action


def restricted(func):
    async def wrapper(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        allowed = context.bot_data.get("allowed_user_id", 0)
        if allowed and user_id != allowed:
            await update.message.reply_text("⛔ Unauthorized")
            return
        return await func(self, update, context)
    return wrapper


class MenuHandler:
    @staticmethod
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        await ensure_user(user.id, user.username or "")
        await log_action(user.id, "start", "success")

        text = (
            f"👋 Bienvenue, {user.first_name}!\n\n"
            "🤖 **Telegram FreeDomain Bot**\n"
            "Gère tes domaines gratuits, emails, DNS, et clés LLM.\n\n"
            "📌 **Commandes principales :**\n"
            "/menu — Menu principal\n"
            "/gmail — Gestion Gmail\n"
            "/cf — Cloudflare DNS\n"
            "/dp — DigitalPlat FreeDomain\n"
            "/keys — Gestion des clés LLM\n"
            "/llm — Configuration LLM\n"
            "/admin — Administration\n"
        )
        await update.message.reply_text(text, parse_mode="Markdown")

    @staticmethod
    async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("📧 Gmail", callback_data="menu_gmail"),
             InlineKeyboardButton("☁️ Cloudflare", callback_data="menu_cf")],
            [InlineKeyboardButton("🌐 DigitalPlat", callback_data="menu_dp"),
             InlineKeyboardButton("🔑 LLM Keys", callback_data="menu_keys")],
            [InlineKeyboardButton("🤖 LLM Chat", callback_data="menu_llm"),
             InlineKeyboardButton("📊 Admin", callback_data="menu_admin")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("📋 **Menu Principal**", reply_markup=reply_markup, parse_mode="Markdown")

    @staticmethod
    async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        data = query.data
        if data == "menu_gmail":
            text = "📧 **Gmail**\n\n/gmail list — Derniers emails\n/gmail read <id> — Lire un email\n/gmail send — Envoyer\n/gmail search <q> — Rechercher\n/gmail summary — Résumé IA"
        elif data == "menu_cf":
            text = "☁️ **Cloudflare**\n\n/cf zones — Zones DNS\n/cf records <zone> — Enregistrements\n/cf add <zone> <type> <name> <val> — Ajouter\n/cf del <zone> <id> — Supprimer"
        elif data == "menu_dp":
            text = "🌐 **DigitalPlat**\n\n/dp login <email> — Connexion\n/dp register <domain> <ext> — Enregistrer\n/dp list — Mes domaines\n/dp check <domain> <ext> — Vérifier dispo"
        elif data == "menu_keys":
            text = "🔑 **LLM Keys**\n\n/keys list — Clés disponibles\n/keys scan <provider> — Scanner GitHub\n/keys register <provider> — Auto-inscription\n/keys test <provider> — Tester une clé"
        elif data == "menu_llm":
            text = "🤖 **LLM**\n\n/llm status — Provider actif\n/llm switch <provider> — Changer\n/llm models — Modèles dispo"
        elif data == "menu_admin":
            text = "📊 **Admin**\n\n/admin — Panneau admin\n/logs — Dernières actions\n/config — Configuration"
        else:
            text = "Menu principal"

        await query.edit_message_text(text, parse_mode="Markdown")
