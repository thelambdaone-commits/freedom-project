import json
from telegram import Update
from telegram.ext import ContextTypes

from bot.agents.cloudflare_agent import CloudflareAgent
from bot.db.repository import log_action


class CloudflareHandler:
    def __init__(self):
        self.agent = CloudflareAgent()

    async def cf_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id

        if not self.agent.is_configured():
            await update.message.reply_text("☁️ Cloudflare non configuré. Ajoute CLOUDFLARE_API_TOKEN dans .env")
            return

        args = context.args
        if not args:
            await update.message.reply_text(
                "☁️ **Cloudflare**\n\n"
                "/cf zones — Zones DNS\n"
                "/cf records <zone> — Enregistrements DNS\n"
                "/cf add <zone> <type> <name> <val> — Ajouter record\n"
                "/cf del <zone> <id> — Supprimer record\n"
                "/cf purge <zone> — Purger le cache\n"
                "/cf dnssec <zone> — Statut DNSSEC",
                parse_mode="Markdown",
            )
            return

        action = args[0]
        try:
            if action == "zones":
                zones = await self.agent.list_zones()
                if not zones:
                    await update.message.reply_text("Aucune zone trouvée.")
                    return
                lines = [
                    f"🌐 **{z['name']}** ({z['status']})\n  ID: `{z['id']}`\n  Plan: {z.get('plan', {}).get('name', 'N/A')}"
                    for z in zones
                ]
                await update.message.reply_text("\n\n".join(lines), parse_mode="Markdown")

            elif action == "records":
                if len(args) < 2:
                    await update.message.reply_text("Usage: /cf records <zone_id_or_name>")
                    return
                zone_id = args[1]
                records = await self.agent.list_dns_records(zone_id)
                if not records:
                    await update.message.reply_text("Aucun enregistrement trouvé.")
                    return
                lines = [
                    f"**{r['name']}** → {r['content']}\n  Type: {r['type']} | TTL: {r['ttl']} | ID: `{r['id']}`"
                    for r in records[:30]
                ]
                await update.message.reply_text("\n\n".join(lines), parse_mode="Markdown")

            elif action == "add":
                if len(args) < 5:
                    await update.message.reply_text("Usage: /cf add <zone_id> <type> <name> <content>")
                    return
                result = await self.agent.create_dns_record(args[1], args[3], args[2].upper(), args[4])
                await update.message.reply_text(f"✅ Record créé: {result.get('result', {}).get('id', 'OK')}")

            elif action == "del":
                if len(args) < 3:
                    await update.message.reply_text("Usage: /cf del <zone_id> <record_id>")
                    return
                await self.agent.delete_dns_record(args[1], args[2])
                await update.message.reply_text("🗑️ Record supprimé.")

            elif action == "purge":
                if len(args) < 2:
                    await update.message.reply_text("Usage: /cf purge <zone_id>")
                    return
                await self.agent.purge_cache(args[1])
                await update.message.reply_text("🧹 Cache purgé.")

            elif action == "dnssec":
                if len(args) < 2:
                    await update.message.reply_text("Usage: /cf dnssec <zone_id>")
                    return
                status = await self.agent.get_dnssec(args[1])
                await update.message.reply_text(f"🔒 DNSSEC: {json.dumps(status.get('result', {}), indent=2)}")

            else:
                await update.message.reply_text(f"Action inconnue: {action}")

            await log_action(user_id, f"cf_{action}", "success")

        except Exception as e:
            await update.message.reply_text(f"❌ Erreur: {str(e)[:300]}")
            await log_action(user_id, f"cf_{action}", "error", str(e))
