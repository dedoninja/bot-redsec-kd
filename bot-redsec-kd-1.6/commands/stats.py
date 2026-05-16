import asyncio
import discord
from config import (
    BOT_SPAM_CHANNEL_ID, ADM_COMMANDS_CHANNEL_ID,
    SERVER_ID, GIF_EA_ID,
)
from database import load_users
from api import fetch_stats
from utils import build_stats_embed


def setup_stats(bot: discord.Bot):

    @bot.slash_command(name="stats", description="Mostra stats completos de um jogador no Redsec")
    @discord.option("gamertag", description="ID da EA", required=True)
    @discord.option("plataforma", description="Plataforma", required=True, choices=["ea", "psn", "xbox", "steam", "epic"])
    async def stats(ctx: discord.ApplicationContext, gamertag: str, plataforma: str):

        # Verificação de ban
        from commands.banlist import is_banned, get_ban_reason
        if is_banned(ctx.author.id, "commands"):
            motivo = get_ban_reason(ctx.author.id, "commands")
            await ctx.respond(f"❌ Você está banido de usar comandos.\nMotivo: {motivo}", ephemeral=True)
            return

        
        spam_channel = bot.get_channel(BOT_SPAM_CHANNEL_ID)
        spam_mention = spam_channel.mention if spam_channel else f"<#{BOT_SPAM_CHANNEL_ID}>"

        if ctx.channel_id not in (BOT_SPAM_CHANNEL_ID, ADM_COMMANDS_CHANNEL_ID):
            await ctx.respond(f"⚠️ Por favor, use os comandos de bot em {spam_mention}.", ephemeral=True)
            return

        await ctx.defer()
        await ctx.followup.send(
            f"<a:buscabf6:1488347979524997171> Buscando stats de **{gamertag}** ({plataforma})...\n"
            f"*Pode demorar até 1 minuto.*"
        )

        # Tenta pegar IDs do banco para usar como Tentativa 0
        users_db = load_users()
        persona_id_db = None
        nucleus_id_db = None
        for uid, info in users_db.items():
            if info.get('gamertag', '').lower() == gamertag.lower() and info.get('platform') == plataforma:
                persona_id_db = info.get('persona_id')
                nucleus_id_db = info.get('nucleus_id')
                break

        data = await asyncio.to_thread(fetch_stats, gamertag, plataforma, persona_id_db, nucleus_id_db)

        if data == "api_error":
            await ctx.followup.send("⚠️ A API de stats está instável no momento. Tente novamente em alguns minutos.")
            return
        if data is None:
            await ctx.followup.send(
                f"❌ ID **{gamertag}** não encontrado na plataforma **{plataforma}**.\n"
                f"Verifique seu **ID da EA**. Como encontrar: {GIF_EA_ID}"
            )
            return

        # Verifica se o jogador está cadastrado no servidor
        guild  = bot.get_guild(SERVER_ID)
        member = None
        registered_at = None
        if guild:
            users = load_users()
            for uid, info in users.items():
                if info.get('gamertag', '').lower() == gamertag.lower() and info.get('platform') == plataforma:
                    member        = guild.get_member(int(uid))
                    registered_at = info.get('registered_at')
                    break

        embed, kd_val, human_pct = build_stats_embed(data, gamertag, plataforma, member, registered_at)
        await ctx.followup.send(embed=embed)
