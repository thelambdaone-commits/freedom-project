import logging
import sys
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from bot.utils.config import settings
from bot.db.connection import get_connection
from bot.handlers.menu import MenuHandler
from bot.handlers.gmail import GmailHandler
from bot.handlers.cloudflare import CloudflareHandler
from bot.handlers.digitalplat import DigitalPlatHandler
from bot.handlers.llm_keys import LLMKeysHandler
from bot.handlers.admin import AdminHandler

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main():
    if not settings.is_telegram_configured:
        logger.error("TELEGRAM_BOT_TOKEN not configured. Copy .env.example to .env and fill it.")
        sys.exit(1)

    if not settings.is_encryption_configured:
        logger.warning("FERNET_KEY not configured. Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"")

    app = Application.builder().token(settings.telegram_bot_token).build()

    app.bot_data["allowed_user_id"] = settings.allowed_user_id

    gmail_handler = GmailHandler()
    cf_handler = CloudflareHandler()
    dp_handler = DigitalPlatHandler()
    llm_handler = LLMKeysHandler()

    app.add_handler(CommandHandler("start", MenuHandler.start))
    app.add_handler(CommandHandler("menu", MenuHandler.menu))
    app.add_handler(CallbackQueryHandler(MenuHandler.menu_callback, pattern="^menu_"))

    app.add_handler(CommandHandler("gmail", gmail_handler.gmail_command))
    app.add_handler(CommandHandler("gmail_auth", gmail_handler.gmail_auth))
    app.add_handler(CommandHandler("gmail_send", gmail_handler.gmail_send))

    app.add_handler(CommandHandler("cf", cf_handler.cf_command))

    app.add_handler(CommandHandler("dp", dp_handler.dp_command))
    app.add_handler(CommandHandler("dp_pass", dp_handler.dp_pass))

    app.add_handler(CommandHandler("keys", llm_handler.keys_command))
    app.add_handler(CommandHandler("llm", llm_handler.llm_command))

    app.add_handler(CommandHandler("admin", AdminHandler.admin_command))
    app.add_handler(CommandHandler("logs", AdminHandler.logs_command))
    app.add_handler(CommandHandler("config", AdminHandler.config_command))

    logger.info("Starting bot...")
    app.run_polling()


if __name__ == "__main__":
    main()
