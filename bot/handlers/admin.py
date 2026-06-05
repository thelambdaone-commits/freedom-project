from telegram import Update
from telegram.ext import ContextTypes

from bot.db.repository import get_logs, log_action
from bot.utils.config import settings


class AdminHandler:
    @staticmethod
    async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        allowed = context.bot_data.get("allowed_user_id", 0)
        if allowed and user_id != allowed:
            await update.message.reply_text("⛔ Unauthorized")
            return

        status_lines = [
            "📊 **Admin Panel**\n",
            f"🔹 Telegram Bot: {'✅' if settings.is_telegram_configured else '❌'}",
            f"🔹 Gmail: {'✅' if settings.is_gmail_configured else '❌'}",
            f"🔹 Cloudflare: {'✅' if settings.is_cloudflare_configured else '❌'}",
            f"🔹 GitHub (KeyHunter): {'✅' if settings.is_github_configured else '❌'}",
            f"🔹 Encryption: {'✅' if settings.is_encryption_configured else '❌'}",
            f"🔹 LLM Provider: {settings.default_llm_provider}",
            "",
            "**Commandes :**",
            "/logs — Dernières actions",
            "/config — Voir la configuration",
        ]
        await update.message.reply_text("\n".join(status_lines), parse_mode="Markdown")

    @staticmethod
    async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        logs = await get_logs(limit=20)
        if not logs:
            await update.message.reply_text("📝 Aucun log pour le moment.")
            return

        lines = []
        for log in logs:
            emoji = "✅" if log["status"] == "success" else "❌"
            time_str = log.get("created_at", "")
            lines.append(f"{emoji} `{log['action']}` — {log['status']}")
        await update.message.reply_text(
            "📝 **Dernières actions :**\n\n" + "\n".join(lines),
            parse_mode="Markdown",
        )

    @staticmethod
    async def config_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        config_preview = (
            f"**Configuration**\n\n"
            f"TELEGRAM_BOT_TOKEN: {'✅ défini' if settings.telegram_bot_token else '❌ manquant'}\n"
            f"ALLOWED_USER_ID: {settings.allowed_user_id}\n"
            f"GMAIL_CLIENT_ID: {'✅ défini' if settings.gmail_client_id else '❌ manquant'}\n"
            f"CLOUDFLARE_API_TOKEN: {'✅ défini' if settings.cloudflare_api_token else '❌ manquant'}\n"
            f"GITHUB_TOKEN: {'✅ défini' if settings.github_token else '❌ manquant'}\n"
            f"FERNET_KEY: {'✅ défini' if settings.fernet_key else '❌ manquant'}\n"
            f"DATABASE_PATH: {settings.database_path}\n"
            f"DEFAULT_LLM_PROVIDER: {settings.default_llm_provider}\n"
            f"OLLAMA_BASE_URL: {settings.ollama_base_url}\n"
        )
        await update.message.reply_text(config_preview, parse_mode="Markdown")
