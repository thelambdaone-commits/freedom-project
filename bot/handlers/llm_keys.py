from telegram import Update
from telegram.ext import ContextTypes

from bot.agents.key_manager import KeyManager, FREE_PROVIDERS
from bot.agents.llm_router import LLMRouter
from bot.db.repository import log_action


class LLMKeysHandler:
    def __init__(self):
        self.key_manager = KeyManager()
        self.llm_router = LLMRouter()

    async def keys_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        args = context.args

        if not args:
            await update.message.reply_text(
                "🔑 **Key Manager**\n\n"
                "/keys list — Clés disponibles\n"
                "/keys scan <provider> — Scanner GitHub pour des clés\n"
                "/keys scan all — Scanner tous les providers\n"
                "/keys test <provider> — Tester une clé\n"
                "/keys register <provider> — Auto-inscription\n"
                "/keys rotate — Forcer la rotation",
                parse_mode="Markdown",
            )
            return

        action = args[0]
        try:
            if action == "list":
                providers = await self.key_manager.list_providers()
                if not providers:
                    await update.message.reply_text("🔑 Aucune clé en base. Lance /keys scan ou /keys register.")
                    return
                lines = []
                for p in providers:
                    lines.append(f"• **{p['provider']}**: {p['key_count']} clé(s)")
                await update.message.reply_text("🔑 **Clés disponibles :**\n\n" + "\n".join(lines), parse_mode="Markdown")

            elif action == "scan":
                if not self.key_manager.is_keyhunter_available:
                    await update.message.reply_text(
                        "❌ key-hunter non trouvé. Clone-le :\n"
                        "git clone https://github.com/thelambdaone-commits/key-hunter"
                    )
                    return

                provider = args[1] if len(args) > 1 else ""
                msg = await update.message.reply_text(f"🔄 Scan GitHub pour {provider or 'tous les providers'}...")
                findings = await self.key_manager.run_keyhunter_scan(provider=provider, verify=True)
                await msg.edit_text(
                    f"✅ Scan terminé ! {len(findings)} clé(s) trouvée(s).\n"
                    "/keys list pour voir les clés disponibles."
                )

            elif action == "test":
                if len(args) < 2:
                    await update.message.reply_text("Usage: /keys test <provider>")
                    return
                msg = await update.message.reply_text(f"🔄 Test de {args[1]}...")
                result = await self.key_manager.test_key(args[1])
                status_emoji = "✅" if result.get("status") == "valid" else "❌"
                await msg.edit_text(f"{status_emoji} **{args[1]}**: {result.get('status')}", parse_mode="Markdown")

            elif action == "register":
                if len(args) < 2:
                    providers_list = "\n".join(f"• {p}" for p in FREE_PROVIDERS)
                    await update.message.reply_text(
                        f"Usage: /keys register <provider>\n\n"
                        f"Providers disponibles:\n{providers_list}",
                    )
                    return
                provider = args[1]
                if provider not in FREE_PROVIDERS:
                    await update.message.reply_text(f"❌ Provider inconnu: {provider}")
                    return
                msg = await update.message.reply_text(f"🔄 Inscription à {provider}...")
                result = await self.key_manager.auto_register_provider(provider)
                await msg.edit_text(
                    f"🔗 Page d'inscription ouverte pour **{provider}** :\n"
                    f"{result.get('signup_url', '')}\n\n"
                    "Tu devras peut-être compléter manuellement.",
                    parse_mode="Markdown",
                    disable_web_page_preview=True,
                )

            elif action == "rotate":
                msg = await update.message.reply_text("🔄 Rotation des clés...")
                providers = await self.key_manager.list_providers()
                rotated = []
                for p in providers:
                    result = await self.key_manager.rotate_key(p["provider"])
                    if result:
                        rotated.append(f"✅ {p['provider']}: OK")
                    else:
                        rotated.append(f"❌ {p['provider']}: aucune clé valide")
                await msg.edit_text("🔄 **Résultat rotation :**\n" + "\n".join(rotated), parse_mode="Markdown")

            else:
                await update.message.reply_text(f"Action inconnue: {action}")

            await log_action(user_id, f"keys_{action}", "success")
        except Exception as e:
            await update.message.reply_text(f"❌ Erreur: {str(e)[:300]}")
            await log_action(user_id, f"keys_{action}", "error", str(e))

    async def llm_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        args = context.args

        if not args:
            config = await self.llm_router.get_provider_config()
            await update.message.reply_text(
                f"🤖 **LLM Router**\n\n"
                f"Provider actif: **{config['provider']}**\n"
                f"Mode: {config.get('api_key', 'N/A')[:20] if config.get('api_key') else 'local (Ollama)'}\n\n"
                "/llm status — Statut détaillé\n"
                "/llm switch <provider> — Changer de provider\n"
                "/llm models — Modèles disponibles\n"
                "/llm ask <question> — Poser une question",
                parse_mode="Markdown",
            )
            return

        action = args[0]
        try:
            if action == "status":
                config = await self.llm_router.get_provider_config()
                await update.message.reply_text(
                    f"🤖 **Statut LLM**\n\n"
                    f"Provider: **{config['provider']}**\n"
                    f"Base URL: `{config['base_url']}`\n"
                    f"Modèle: {config.get('model', 'auto')}",
                    parse_mode="Markdown",
                )

            elif action == "switch":
                if len(args) < 2:
                    await update.message.reply_text("Usage: /llm switch <provider>")
                    return
                self.llm_router.current_provider = args[1]
                await update.message.reply_text(f"✅ Provider changé pour **{args[1]}**", parse_mode="Markdown")

            elif action == "models":
                await update.message.reply_text(
                    "**Modèles par provider :**\n\n"
                    "Ollama: llama3, mistral, qwen2.5\n"
                    "OpenRouter: 20+ modèles gratuits\n"
                    "Groq: llama-3.3-70b, qwen-32b\n"
                    "Google: gemini-2.5-flash\n"
                    "GitHub Models: gpt-4.1, claude\n"
                    "Cloudflare: 30+ modèles",
                    parse_mode="Markdown",
                )

            elif action == "ask":
                question = " ".join(args[1:])
                if not question:
                    await update.message.reply_text("Usage: /llm ask <question>")
                    return
                msg = await update.message.reply_text("🤖 Réflexion en cours...")
                response = await self.llm_router.chat_completion(
                    [{"role": "user", "content": question}]
                )
                await msg.edit_text(response[:4000])

            else:
                await update.message.reply_text(f"Action inconnue: {action}")

            await log_action(user_id, f"llm_{action}", "success")
        except Exception as e:
            await update.message.reply_text(f"❌ Erreur: {str(e)[:200]}")
            await log_action(user_id, f"llm_{action}", "error", str(e))
