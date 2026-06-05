from telegram import Update
from telegram.ext import ContextTypes

from bot.agents.gmail_agent import GmailAgent
from bot.db.repository import log_action


class GmailHandler:
    def __init__(self):
        pass

    @staticmethod
    async def gmail_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        agent = GmailAgent(user_id)
        authenticated = await agent.ensure_authenticated()

        if not authenticated:
            auth_url = agent.get_auth_url()
            await update.message.reply_text(
                "🔐 **Gmail non connecté**\n\n"
                "1. Clique sur le lien pour autoriser :\n"
                f"{auth_url}\n\n"
                "2. Copie le code de callback et envoie :\n"
                "/gmail_auth <code>",
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )
            return

        args = context.args
        if not args:
            await update.message.reply_text(
                "📧 **Gmail**\n\n"
                "/gmail list [n] — Derniers emails\n"
                "/gmail read <id> — Lire un email\n"
                "/gmail send — Envoyer (interactif)\n"
                "/gmail search <q> — Rechercher\n"
                "/gmail delete <id> — Supprimer\n"
                "/gmail archive <id> — Archiver\n"
                "/gmail labels — Labels\n"
                "/gmail summary — Résumé IA",
                parse_mode="Markdown",
            )
            return

        action = args[0]
        try:
            if action == "list":
                n = int(args[1]) if len(args) > 1 else 10
                emails = await agent.list_emails(max_results=min(n, 50))
                if not emails:
                    await update.message.reply_text("📭 Aucun email trouvé.")
                    return
                lines = [f"📧 **{e['subject'][:50]}**\n  De: {e['from'][:40]}\n  `/gmail read {e['id']}`" for e in emails]
                await update.message.reply_text("\n\n".join(lines), parse_mode="Markdown")

            elif action == "read":
                if len(args) < 2:
                    await update.message.reply_text("Usage: /gmail read <id>")
                    return
                email = await agent.read_email(args[1])
                text = (
                    f"**De:** {email['from']}\n"
                    f"**Sujet:** {email['subject']}\n"
                    f"**Date:** {email['date']}\n\n"
                    f"{email['body'][:2000] if email['body'] else email['snippet'][:2000]}"
                )
                await update.message.reply_text(text, parse_mode="Markdown")

            elif action == "send":
                await update.message.reply_text(
                    "Pour envoyer un email, utilise :\n"
                    "/gmail_send <destinataire> <sujet> <message>"
                )

            elif action == "search":
                query = " ".join(args[1:])
                if not query:
                    await update.message.reply_text("Usage: /gmail search <query>")
                    return
                emails = await agent.search_emails(query)
                if not emails:
                    await update.message.reply_text("Aucun résultat.")
                    return
                lines = [f"📧 **{e['subject'][:50]}**\n  De: {e['from'][:40]}" for e in emails[:10]]
                await update.message.reply_text("\n\n".join(lines), parse_mode="Markdown")

            elif action == "delete":
                if len(args) < 2:
                    await update.message.reply_text("Usage: /gmail delete <id>")
                    return
                await agent.delete_email(args[1])
                await update.message.reply_text("🗑️ Email déplacé vers la corbeille.")

            elif action == "archive":
                if len(args) < 2:
                    await update.message.reply_text("Usage: /gmail archive <id>")
                    return
                await agent.modify_email(args[1], remove_labels=["INBOX"])
                await update.message.reply_text("📦 Email archivé.")

            elif action == "labels":
                labels = await agent.list_labels()
                lines = [f"🏷️ {l['name']} ({l['type']})" for l in labels[:30]]
                await update.message.reply_text("\n".join(lines) if lines else "Aucun label.")

            elif action == "summary":
                emails = await agent.list_emails(max_results=10)
                from bot.agents.llm_router import LLMRouter
                router = LLMRouter()
                summary = await router.summarize_emails(emails)
                await update.message.reply_text(f"📋 **Résumé emails :**\n\n{summary}", parse_mode="Markdown")

            else:
                await update.message.reply_text(f"Action inconnue: {action}")

            await log_action(user_id, f"gmail_{action}", "success")

        except Exception as e:
            await update.message.reply_text(f"❌ Erreur: {str(e)[:200]}")
            await log_action(user_id, f"gmail_{action}", "error", str(e))

    @staticmethod
    async def gmail_auth(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        code = " ".join(context.args) if context.args else ""
        if not code:
            await update.message.reply_text("Usage: /gmail_auth <code>")
            return

        try:
            agent = GmailAgent(user_id)
            await agent.handle_callback(code)
            await update.message.reply_text("✅ Gmail connecté avec succès !")
            await log_action(user_id, "gmail_auth", "success")
        except Exception as e:
            await update.message.reply_text(f"❌ Erreur d'authentification: {str(e)[:200]}")
            await log_action(user_id, "gmail_auth", "error", str(e))

    @staticmethod
    async def gmail_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        args = context.args
        if len(args) < 3:
            await update.message.reply_text("Usage: /gmail_send <to> <subject> <message>")
            return

        to = args[0]
        subject = args[1]
        body = " ".join(args[2:])

        try:
            agent = GmailAgent(user_id)
            if not await agent.ensure_authenticated():
                await update.message.reply_text("🔐 Gmail non connecté.")
                return
            msg_id = await agent.send_email(to, subject, body)
            await update.message.reply_text(f"✅ Email envoyé (ID: {msg_id})")
            await log_action(user_id, "gmail_send", "success")
        except Exception as e:
            await update.message.reply_text(f"❌ Erreur: {str(e)[:200]}")
            await log_action(user_id, "gmail_send", "error", str(e))
