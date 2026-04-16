import asyncio
import discord
from datetime import datetime
from config import (
    BOT_SPAM_CHANNEL_ID, ADM_COMMANDS_CHANNEL_ID,
    LOGS_CHANNEL_ID,
    GIF_EA_ID, GIF_DataShare,
)
from database import load_users, save_users
from api import fetch_stats, resolve_player_ids, make_links
from utils import extract_kd_and_human, extract_kd_by_mode, apply_roles


def setup_kd(bot: discord.Bot):

    @bot.slash_command(name="kd", description="Busca seu KD no Redsec e atribui role")
    @discord.option("gamertag", description="Seu ID da EA", required=True)
    @discord.option("plataforma", description="Plataforma", required=True, choices=["pc", "psn", "xbox"])
    async def kd(ctx: discord.ApplicationContext, gamertag: str, plataforma: str):
        spam_channel = bot.get_channel(BOT_SPAM_CHANNEL_ID)
        spam_mention = spam_channel.mention if spam_channel else f"<#{BOT_SPAM_CHANNEL_ID}>"

        if ctx.channel_id not in (BOT_SPAM_CHANNEL_ID, ADM_COMMANDS_CHANNEL_ID):
            await ctx.respond(
                f"⚠️ Por favor, use os comandos de bot em {spam_mention}.",
                ephemeral=True
            )
            return

        # Verificação de ban
        from commands.banlist import is_banned, get_ban_reason
        if is_banned(ctx.author.id, "commands"):
            motivo = get_ban_reason(ctx.author.id, "commands")
            await ctx.respond(f"❌ Você está banido de usar comandos.\nMotivo: {motivo}", ephemeral=True)
            return
        if is_banned(ctx.author.id, "register"):
            motivo = get_ban_reason(ctx.author.id, "register")
            await ctx.respond(f"❌ Você está banido de se registrar no bot.\nMotivo: {motivo}", ephemeral=True)
            return

        await ctx.defer()

        await ctx.followup.send(
            f"<a:buscabf6:1488347979524997171> Buscando KD **Redsec** de **{gamertag}** ({plataforma})...\n"
            f"*Pode demorar até 1 minuto.*"
        )

        data = await asyncio.to_thread(fetch_stats, gamertag, plataforma)

        if data == "api_error":
            await ctx.followup.send(
                f"⚠️ A API de stats está instável no momento.\n"
                f"Tente novamente em alguns minutos."
            )
            return
        if data is None:
            await ctx.followup.send(
                f"❌ ID **{gamertag}** não encontrado na plataforma **{plataforma}**.\n"
                f"Verifique seu **ID da EA**. Como encontrar: {GIF_EA_ID}"
            )
            return

        kd_val, human_pct = extract_kd_and_human(data)

        if kd_val == 0.0:
            await ctx.followup.send(
                f"⚠️ **{gamertag}** sem stats no **Redsec** ainda.\n"
                f"- Jogue mais partidas de Redsec.\n"
                f"- Ative o 'Gameplay Data Sharing' no BF6. Veja como: <{GIF_DataShare}>\n"
                f"- Use o **ID da EA** correto. Veja aqui: {GIF_EA_ID}"
            )
            return

        guild = bot.get_guild(ctx.guild_id)
        if not guild:
            await ctx.followup.send("❌ Erro interno: servidor não encontrado. Contate a staff!")
            return

        changes = await apply_roles(ctx.author, guild, kd_val, human_pct)

        # Salva no JSON (igual ao botão de registro)
        users_data  = load_users()
        disc_id_str = str(ctx.author.id)
        old_entry   = users_data.get(disc_id_str)
        pid, nid    = await asyncio.to_thread(resolve_player_ids, gamertag)
        entry_kd    = {
            "gamertag":      gamertag,
            "platform":      plataforma,
            "registered_at": datetime.utcnow().isoformat()
        }
        if pid and nid:
            entry_kd["persona_id"] = pid
            entry_kd["nucleus_id"] = nid
        users_data[disc_id_str] = entry_kd
        save_users(users_data)

        # Log no canal de logs (com ⚠️ se suspeito)
        logs_ch = bot.get_channel(LOGS_CHANNEL_ID)
        if logs_ch:
            action_log  = "atualizado" if old_entry else "registrado"
            is_sus_log  = changes['suspeita_interno'] not in ["Honesto", "Human% indisponível"]
            human_label = f"⚠️ Human%: **{human_pct:.2f}%**" if is_sus_log else f"Human%: **{human_pct:.2f}%**"
            await logs_ch.send(
                f"📋 **Registro via /kd** | {ctx.author.mention} (`{ctx.author.id}`) | Ação: **{action_log}**\n"
                f"Gamertag: `{gamertag}` | Plataforma: `{plataforma}`\n"
                f"KD: **{kd_val:.2f}** → **{changes['kd_role']}** | {human_label} | "
                f"{make_links(gamertag, plataforma, pid, nid)}"
            )

        kd_modos = extract_kd_by_mode(data)
        if old_entry:
            nota = "ℹ️ Seus dados já estavam cadastrados e foram atualizados. O bot atualiza sua role automaticamente todo dia às 04:00!"
        else:
            nota = "✅ Seus dados foram salvos! O bot atualizará sua role automaticamente todo dia às 04:00."
        await ctx.followup.send(
            f"✅ KD **Redsec** atual: **{kd_val:.2f}**\n"
            f"Role atribuída: **{changes['kd_role']}**\n"
            f"KD Squad: **{kd_modos['Squad']:.2f}** | KD Duo: **{kd_modos['Duo']:.2f}** | "
            f"KD Solo: **{kd_modos['Solo']:.2f}** | KD Gauntlet: **{kd_modos['Gauntlet']:.2f}**\n"
            f"Status: **{changes['suspeita_publico']}**\n\n"
            f"{nota}"
        )
