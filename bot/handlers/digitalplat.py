from telegram import Update
from telegram.ext import ContextTypes

from bot.agents.digitalplat_agent import DigitalPlatAgent
from bot.db.repository import log_action


class DigitalPlatHandler:
    @staticmethod
    async def dp_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        agent = DigitalPlatAgent(user_id)

        args = context.args
        if not args:
            await update.message.reply_text(
                "🌐 **DigitalPlat FreeDomain**\n\n"
                "/dp login <email> — Connexion au dashboard\n"
                "/dp register <domain> <ext> — Enregistrer un domaine\n"
                "/dp list — Mes domaines\n"
                "/dp check <domain> <ext> — Vérifier disponibilité\n"
                "/dp status <domain> — Statut d'un domaine\n"
                "/dp ns <domain> <ns1> [ns2] — Changer nameservers (via Cloudflare)",
                parse_mode="Markdown",
            )
            return

        action = args[0]
        try:
            if action == "login":
                if len(args) < 2:
                    await update.message.reply_text(
                        "Usage: /dp login <email>\n"
                        "Le bot te demandera le mot de passe en message privé."
                    )
                    return
                email = args[1]
                await update.message.reply_text(
                    f"🔐 Envoie ton mot de passe pour **{email}** en MP.\n"
                    "Format: /dp_pass <mot_de_passe>",
                    parse_mode="Markdown",
                )
                context.user_data["dp_login_email"] = email

            elif action == "register":
                if len(args) < 3:
                    await update.message.reply_text(
                        "Usage: /dp register <domain> <extension>\n"
                        "Extensions: us.kg, xx.kg, dpdns.org, qzz.io"
                    )
                    return
                msg = await update.message.reply_text("🔄 Enregistrement du domaine en cours...")
                result = await agent.register_domain(args[1], args[2])
                await msg.edit_text(
                    f"✅ Domaine soumis: **{result.get('domain', '?')}**\n"
                    f"Statut: {result.get('status', '?')}",
                    parse_mode="Markdown",
                )

            elif action == "list":
                msg = await update.message.reply_text("🔄 Récupération de tes domaines...")
                domains = await agent.list_my_domains()
                if not domains:
                    await msg.edit_text("Aucun domaine trouvé.")
                    return
                lines = [f"🌐 **{d['domain']}**" for d in domains]
                await msg.edit_text("\n".join(lines), parse_mode="Markdown")

            elif action == "check":
                if len(args) < 3:
                    await update.message.reply_text("Usage: /dp check <domain> <extension>")
                    return
                result = await agent.check_availability(args[1], args[2])
                if result.get("available") is True:
                    await update.message.reply_text(f"✅ **{result['domain']}** est disponible !")
                elif result.get("available") is False:
                    await update.message.reply_text(f"❌ **{result['domain']}** est déjà pris.")
                else:
                    await update.message.reply_text(f"❓ Incertain: {result.get('response', '')[:200]}")

            elif action == "status":
                if len(args) < 2:
                    await update.message.reply_text("Usage: /dp status <domain>")
                    return
                status = await agent.get_domain_status(args[1])
                ns_text = ", ".join(status.get("nameservers", [])) or "Non configuré"
                await update.message.reply_text(
                    f"🌐 **{status['domain']}**\n\n"
                    f"Nameservers: {ns_text}",
                    parse_mode="Markdown",
                )

            elif action == "ns":
                await update.message.reply_text(
                    "Pour configurer les nameservers, utilise plutôt:\n"
                    "/cf add <zone> NS <name> <nameserver>"
                )

            else:
                await update.message.reply_text(f"Action inconnue: {action}")

            await log_action(user_id, f"dp_{action}", "success")

        except Exception as e:
            await update.message.reply_text(f"❌ Erreur: {str(e)[:300]}")
            await log_action(user_id, f"dp_{action}", "error", str(e))
        finally:
            await agent.close()

    @staticmethod
    async def dp_pass(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        email = context.user_data.get("dp_login_email", "")
        if not email:
            await update.message.reply_text("❌ Utilise d'abord /dp login <email>")
            return

        password = " ".join(context.args) if context.args else ""
        if not password:
            await update.message.reply_text("Usage: /dp_pass <mot_de_passe>")
            return

        agent = DigitalPlatAgent(user_id)
        try:
            msg = await update.message.reply_text("🔄 Connexion au dashboard...")
            result = await agent.login(email, password)
            await msg.edit_text(
                f"✅ Connecté !\n{result.get('url', 'Dashboard prêt.')}"
            )
            await log_action(user_id, "dp_login", "success")
        except Exception as e:
            await update.message.reply_text(f"❌ Erreur de connexion: {str(e)[:300]}")
            await log_action(user_id, "dp_login", "error", str(e))
        finally:
            await agent.close()
