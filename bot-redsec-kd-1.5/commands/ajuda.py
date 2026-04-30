import discord
from config import (
    BOT_SPAM_CHANNEL_ID, REGISTER_CHANNEL_ID, GIF_EA_ID,
)


def setup_ajuda(bot: discord.Bot):

    @bot.slash_command(name="ajuda", description="Mostra como usar o bot")
    async def ajuda(ctx: discord.ApplicationContext):

        # Verificação de ban
        from commands.banlist import is_banned, get_ban_reason
        if is_banned(ctx.author.id, "commands"):
            motivo = get_ban_reason(ctx.author.id, "commands")
            await ctx.respond(f"❌ Você está banido de usar comandos.\nMotivo: {motivo}", ephemeral=True)
            return

        
        spam_channel = bot.get_channel(BOT_SPAM_CHANNEL_ID)
        spam_mention = spam_channel.mention if spam_channel else f"<#{BOT_SPAM_CHANNEL_ID}>"

        register_channel = bot.get_channel(REGISTER_CHANNEL_ID)
        register_mention = register_channel.mention if register_channel else f"<#{REGISTER_CHANNEL_ID}>"

        embed = discord.Embed(
            title="Como usar o bot de KD Redsec",
            description=(
                f"Vá até o canal {register_mention} e clique no botão **⭕ Registre-se aqui!**\n"
                "Após registrar, o bot atualiza suas roles automaticamente a cada **24 horas**.\n\n"
                f"**Comandos manuais** (use em {spam_mention}):\n"
                f"→ `/kd [SeuID] [plataforma]` — busca seu KD e atribui a role\n"
                f"→ `/stats [IDdaEA] [plataforma]` — stats completos (KD, Human%, Accuracy...)\n"
                f"→ `/minha_conta` — veja seus próprios stats e dados de cadastro\n"
                f"→ `/top5 [Categoria]` — veja os top 5 players com maior KD na categoria selecionada\n\n"
                "**Plataformas válidas:** `ea` · `psn` · `xbox` · `steam` · `epic`\n\n"
                "**Como pegar seu ID da EA?** Veja o GIF abaixo!\n\n"
                "Qualquer dúvida, chama a staff!"
            ),
            color=discord.Color.blue()
        )
        embed.set_image(url=GIF_EA_ID)
        await ctx.respond(embed=embed)
