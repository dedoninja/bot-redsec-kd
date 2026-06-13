import asyncio
import discord
from config import (
    BOT_SPAM_CHANNEL_ID, ADM_COMMANDS_CHANNEL_ID,
    REGISTER_CHANNEL_ID, GIF_DataShare,
)
from database import load_users
from api import fetch_stats, fetch_competitive_rank
from utils import build_stats_embed


def setup_minha_conta(bot: discord.Bot):

    @bot.slash_command(name="minha_conta", description="Mostra seus stats e dados de cadastro")
    async def minha_conta(ctx: discord.ApplicationContext):

        # Verificação de ban
        from commands.banlist import is_banned, get_ban_reason
        if is_banned(ctx.author.id, "commands"):
            motivo = get_ban_reason(ctx.author.id, "commands")
            await ctx.respond(f"❌ Você está banido de usar comandos.\nMotivo: {motivo}", ephemeral=True)
            return

        
        spam_channel = bot.get_channel(BOT_SPAM_CHANNEL_ID)
        spam_mention = spam_channel.mention if spam_channel else f"<#{BOT_SPAM_CHANNEL_ID}>"

        if ctx.channel_id not in (BOT_SPAM_CHANNEL_ID, ADM_COMMANDS_CHANNEL_ID):
            await ctx.respond(f"⚠️ Por favor, use este comando em {spam_mention}.", ephemeral=True)
            return

        users      = load_users()
        discord_id = str(ctx.author.id)
        if discord_id not in users:
            register_channel = bot.get_channel(REGISTER_CHANNEL_ID)
            register_mention = register_channel.mention if register_channel else "canal de registro"
            await ctx.respond(
                f"❌ Você ainda não está cadastrado!\n"
                f"Vá até {register_mention} e clique em **⭕ Registre-se aqui!**",
                ephemeral=True
            )
            return

        info          = users[discord_id]
        gt            = info.get('gamertag', '?')
        plat          = info.get('platform', 'ea')
        registered_at = info.get('registered_at', '')
        persona_id    = info.get('persona_id')
        nucleus_id    = info.get('nucleus_id')

        await ctx.defer()
        await ctx.followup.send(
            f"<a:buscabf6:1488347979524997171> Buscando seus stats (**{gt}** | {plat})..."
        )

        data = await asyncio.to_thread(fetch_stats, gt, plat, persona_id, nucleus_id)

        if data == "api_error":
            await ctx.followup.send("⚠️ A API de stats está instável. Tente novamente em alguns minutos.")
            return
        if data is None:
            await ctx.followup.send("❌ Não foi possível encontrar seus stats. Verifique seu cadastro.")
            return

        # Busca rank competitivo para exibir no embed
        comp_rank_mc, comp_rank_name_mc = await asyncio.to_thread(fetch_competitive_rank, persona_id, nucleus_id)

        embed, _, _ = build_stats_embed(
            data, gt, plat, ctx.author, registered_at,
            comp_rank=comp_rank_mc,
            comp_rank_name=comp_rank_name_mc,
        )
        await ctx.followup.send(embed=embed)

        # Aviso de perfil privado (somente se perfil realmente privado, não Unranked)
        if comp_rank_name_mc == 'Perfil Privado':
            await ctx.followup.send(
                f"{ctx.author.mention} seu **Compartilhamento de dados** está desativado. "
                f"Habilite em: Opções → Sistema → Compartilhamento de dados de gameplay.\n"
                f"{GIF_DataShare}",
                ephemeral=True
            )
