import discord
from config import LOGS_CHANNEL_ID
from voice import _temp_voice_channels
from config import VOICE_TARGET_CATEGORIES, VOICE_PROTECTED_CHANNELS, VOICE_TRIGGER_MAP


def _get_temp_channel_of_member(member: discord.Member):
    """
    Retorna o canal de voz temporário do qual o member é criador,
    ou None se ele não for criador de nenhuma sala temporária.

    A verificação usa a permissão 'move_members' no canal, que é concedida
    exclusivamente ao criador no momento da criação da sala.
    """
    guild = member.guild
    for channel in guild.voice_channels:
        # Só canais nas categorias monitoradas
        if not channel.category_id or channel.category_id not in VOICE_TARGET_CATEGORIES:
            continue
        # Nunca conta canais protegidos ou triggers
        if channel.id in VOICE_PROTECTED_CHANNELS or channel.id in VOICE_TRIGGER_MAP:
            continue
        # Checa se o member tem overwrite de move_members (marca do criador)
        overwrite = channel.overwrites_for(member)
        if overwrite.move_members is True:
            return channel
    return None


def setup_voice_ban(bot: discord.Bot):

    @bot.slash_command(name="ban_sala", description="Bane um usuário da sua sala de voz temporária")
    @discord.option("usuario", description="Usuário a ser banido da sala", type=discord.Member, required=True)
    async def ban_sala(ctx: discord.ApplicationContext, usuario: discord.Member):

        # Verifica se o autor possui uma sala temporária (é criador)
        sala = _get_temp_channel_of_member(ctx.author)

        if sala is None:
            await ctx.respond(
                "❌ Você não é criador de nenhuma sala temporária ativa.",
                ephemeral=True
            )
            return

        # Não pode banir a si mesmo
        if usuario.id == ctx.author.id:
            await ctx.respond("❌ Você não pode banir a si mesmo da sala.", ephemeral=True)
            return

        # Não pode banir bots
        if usuario.bot:
            await ctx.respond("❌ Você não pode banir bots da sala.", ephemeral=True)
            return

        # Aplica overwrite impedindo o usuário de entrar na sala
        try:
            overwrite = discord.PermissionOverwrite(connect=False)
            await sala.set_permissions(usuario, overwrite=overwrite, reason=f"Ban de sala por {ctx.author}")
        except discord.Forbidden:
            await ctx.respond("❌ Não tenho permissão para modificar as permissões desta sala.", ephemeral=True)
            return
        except Exception as e:
            await ctx.respond(f"❌ Erro ao aplicar ban: {e}", ephemeral=True)
            return

        # Desconecta o usuário se ele estiver na sala
        if usuario.voice and usuario.voice.channel and usuario.voice.channel.id == sala.id:
            try:
                await usuario.move_to(None, reason=f"Banido da sala por {ctx.author}")
            except discord.Forbidden:
                pass  # Não interrompe o fluxo se não conseguir desconectar
            except Exception:
                pass

        # Confirmação para o criador (ephemeral)
        await ctx.respond(
            f"✅ **{usuario.display_name}** foi banido da sala **{sala.name}** e desconectado.",
            ephemeral=True
        )

        # Log no canal de logs
        logs_ch = bot.get_channel(LOGS_CHANNEL_ID)
        if logs_ch:
            await logs_ch.send(
                f"🔇 **Ban de sala** | "
                f"Criador: {ctx.author.mention} (`{ctx.author}`) | "
                f"Banido: {usuario.mention} (`{usuario}`) | "
                f"Sala: **{sala.name}**"
            )
