import asyncio
import discord
from discord.ui import Button, View, Modal, InputText
from datetime import datetime, timezone, timedelta
from config import (
    SERVER_ID, REGISTER_CHANNEL_ID, BOT_SPAM_CHANNEL_ID,
    ADM_CHAT_CHANNEL_ID, ADM_COMMANDS_CHANNEL_ID, LOGS_CHANNEL_ID,
    GIF_EA_ID, GIF_DataShare,
    VOICE_TARGET_CATEGORIES, VOICE_PROTECTED_CHANNELS, VOICE_TRIGGER_MAP,
    VOICE_CATEGORY_NAMES,
)
from database import load_users, save_users
from api import fetch_stats, resolve_player_ids, make_links
from utils import extract_kd_and_human, extract_kd_by_mode, build_stats_embed, apply_roles


# ================== MODAL DE REGISTRO ==================
class RegisterModal(Modal):
    def __init__(self, bot: discord.Bot):
        super().__init__(title="Registre sua conta EA")
        self._bot = bot
        self.add_item(InputText(
            label="Qual é o seu ID EA?",
            placeholder="Ex: Hinachiwar",
            required=True,
            max_length=64
        ))
        self.add_item(InputText(
            label="Plataforma (pc, psn ou xbox)",
            placeholder="pc",
            required=True,
            max_length=4
        ))

    async def callback(self, interaction: discord.Interaction):
        bot         = self._bot
        gamertag    = self.children[0].value.strip()
        platform_raw = self.children[1].value.strip().lower()

        if platform_raw not in ['pc', 'psn', 'xbox']:
            await interaction.response.send_message(
                "❌ Plataforma inválida. Use **pc**, **psn** ou **xbox**.",
                ephemeral=True
            )
            logs_ch = bot.get_channel(LOGS_CHANNEL_ID)
            if logs_ch:
                await logs_ch.send(
                    f"📋 **Registro** | {interaction.user.mention} (`{interaction.user.id}`)\n"
                    f"Gamertag: `{gamertag}` | Plataforma: `{platform_raw}`\n"
                    f"❌ Erro: Plataforma inválida informada."
                )
            return

        await interaction.response.send_message(
            f"<a:buscabf6:1488347979524997171> Registrando **{gamertag}** ({platform_raw})... *Pode demorar até 1 minuto.*",
            ephemeral=True
        )

        data = await asyncio.to_thread(fetch_stats, gamertag, platform_raw)

        if data == "api_error":
            await interaction.followup.send(
                f"⚠️ A API de stats está instável no momento.\n"
                f"Tente se registrar novamente em alguns minutos.",
                ephemeral=True
            )
            logs_ch = bot.get_channel(LOGS_CHANNEL_ID)
            if logs_ch:
                await logs_ch.send(
                    f"📋 **Registro** | {interaction.user.mention} (`{interaction.user.id}`)\n"
                    f"Gamertag: `{gamertag}` | Plataforma: `{platform_raw}`\n"
                    f"❌ Erro: API de stats instável."
                )
            return
        if data is None:
            await interaction.followup.send(
                f"❌ ID **{gamertag}** não encontrado na plataforma **{platform_raw}**.\n"
                f"Verifique seu **ID da EA**. Como encontrar: {GIF_EA_ID}",
                ephemeral=True
            )
            logs_ch = bot.get_channel(LOGS_CHANNEL_ID)
            if logs_ch:
                await logs_ch.send(
                    f"📋 **Registro** | {interaction.user.mention} (`{interaction.user.id}`)\n"
                    f"Gamertag: `{gamertag}` | Plataforma: `{platform_raw}`\n"
                    f"❌ Erro: ID não encontrado na API."
                )
            return

        kd_val, human_pct = extract_kd_and_human(data)

        if kd_val == 0.0:
            await interaction.followup.send(
                f"⚠️ **{gamertag}** ainda não tem partidas no **Redsec**.\n\n"
                f"❌ **Seu nick NÃO foi salvo** e não receberá atualização automática de roles.\n"
                f"Volte e se registre novamente após jogar partidas de Redsec!\n\n"
                f"**O que fazer:**\n"
                f"- Jogue partidas no modo Redsec.\n"
                f"- Ative o 'Gameplay Data Sharing' no BF6. Veja como: <{GIF_DataShare}>\n"
                f"- Certifique-se de usar o **ID da EA** correto. Veja como: {GIF_EA_ID}",
                ephemeral=True
            )
            logs_ch = bot.get_channel(LOGS_CHANNEL_ID)
            if logs_ch:
                await logs_ch.send(
                    f"📋 **Registro** | {interaction.user.mention} (`{interaction.user.id}`)\n"
                    f"Gamertag: `{gamertag}` | Plataforma: `{platform_raw}`\n"
                    f"❌ Erro: Sem partidas no Redsec."
                )
            return

        # Resolve e salva persona_id/nucleus_id junto com o registro
        persona_id, nucleus_id = await asyncio.to_thread(resolve_player_ids, gamertag)

        users      = load_users()
        discord_id = str(interaction.user.id)
        old_entry  = users.get(discord_id)
        entry = {
            "gamertag":      gamertag,
            "platform":      platform_raw,
            "registered_at": datetime.utcnow().isoformat()
        }
        if persona_id and nucleus_id:
            entry["persona_id"] = persona_id
            entry["nucleus_id"] = nucleus_id
        users[discord_id] = entry
        save_users(users)

        # Aplica roles
        guild = bot.get_guild(SERVER_ID)
        changes = {'kd_role': '?', 'suspeita_interno': '?', 'suspeita_publico': '?'}
        if guild:
            member = guild.get_member(interaction.user.id)
            if member:
                changes = await apply_roles(member, guild, kd_val, human_pct)

                # Loga suspeita no canal de logs (destacado com ⚠️)
                if changes['suspeita_interno'] not in ["Honesto", "Human% indisponível"]:
                    _logs_sus = bot.get_channel(LOGS_CHANNEL_ID)
                    if _logs_sus:
                        await _logs_sus.send(
                            f"📋 **Registro** | ⚠️ Suspeita detectada | {interaction.user.mention} (`{interaction.user.id}`)\n"
                            f"Gamertag: **{gamertag}** ({platform_raw})\n"
                            f"KD: **{kd_val:.2f}** → **{changes['kd_role']}** | ⚠️ Human%: **{human_pct:.2f}%** → **{changes['suspeita_interno']}** | "
                            f"{make_links(gamertag, platform_raw, persona_id, nucleus_id)}"
                        )

        kd_modos = extract_kd_by_mode(data)
        action = "atualizado" if old_entry else "registrado"
        if old_entry:
            nota_modal = "ℹ️ Seus dados já estavam cadastrados e foram atualizados. O bot atualiza sua role automaticamente todo dia às 04:00!"
        else:
            nota_modal = "✅ Seus dados foram salvos! O bot atualizará sua role automaticamente todo dia às 04:00."
        await interaction.followup.send(
            f"✅ Nick **{action}** com sucesso!\n"
            f"Gamertag: **{gamertag}** ({platform_raw})\n"
            f"KD Redsec: **{kd_val:.2f}** → Role: **{changes['kd_role']}**\n"
            f"KD Squad: **{kd_modos['Squad']:.2f}** | KD Duo: **{kd_modos['Duo']:.2f}** | "
            f"KD Solo: **{kd_modos['Solo']:.2f}** | KD Gauntlet: **{kd_modos['Gauntlet']:.2f}**\n"
            f"Status: **{changes['suspeita_publico']}**\n\n"
            f"{nota_modal}",
            ephemeral=True
        )
        logs_ch = bot.get_channel(LOGS_CHANNEL_ID)
        if logs_ch:
            is_sus_log  = changes['suspeita_interno'] not in ["Honesto", "Human% indisponível"]
            human_label = f"⚠️ Human%: **{human_pct:.2f}%**" if is_sus_log else f"Human%: **{human_pct:.2f}%**"
            await logs_ch.send(
                f"📋 **Registro** | {interaction.user.mention} (`{interaction.user.id}`) | Ação: **{action}**\n"
                f"Gamertag: `{gamertag}` | Plataforma: `{platform_raw}`\n"
                f"KD: **{kd_val:.2f}** → **{changes['kd_role']}** | {human_label} | "
                f"{make_links(gamertag, platform_raw, persona_id, nucleus_id)}"
            )


# ================== BOTÃO DE REGISTRO ==================
class RegisterView(View):
    def __init__(self, bot: discord.Bot = None):
        super().__init__(timeout=None)
        self._bot = bot

    @discord.ui.button(label="⭕ Registre-se aqui!", style=discord.ButtonStyle.primary, custom_id="register_button")
    async def register_button(self, button: Button, interaction: discord.Interaction):
        await interaction.response.send_modal(RegisterModal(self._bot))


# ================== COMANDOS ADMIN ==================
def setup_admin(bot: discord.Bot):

    @bot.slash_command(name="generate_register", description="[ADMIN] Envia o painel de registro no canal fixo")
    @discord.default_permissions(administrator=True)
    async def generate_register(ctx: discord.ApplicationContext):
        channel = bot.get_channel(REGISTER_CHANNEL_ID)
        if not channel:
            await ctx.respond("❌ Canal de registro não encontrado. Verifique o REGISTER_CHANNEL_ID no bot.", ephemeral=True)
            return

        spam_channel = bot.get_channel(BOT_SPAM_CHANNEL_ID)
        spam_mention = spam_channel.mention if spam_channel else f"<#{BOT_SPAM_CHANNEL_ID}>"

        embed = discord.Embed(
            title="Registre-se com sua conta EA para obter a role baseada no seu KD.",
            description=(
                f"Clique no botão abaixo, informe seu **ID da EA** e a **plataforma** para receber sua role automaticamente!\n\n"
                f"**Como encontrar seu ID da EA?** Veja o GIF abaixo.\n\n"
                f"Para usar os comandos manuais `/kd` e `/stats`, acesse {spam_mention}.\n"
                f"Dúvidas? Use `/ajuda`.\n\n"
                f"🟢 [Verificar se o bot está online](https://bot-redsec-kd.fly.dev/)"
            ),
            color=discord.Color.blue()
        )
        embed.set_image(url=GIF_EA_ID)

        await channel.send(embed=embed, view=RegisterView(bot))
        await ctx.respond(f"✅ Painel de registro enviado em {channel.mention}!", ephemeral=True)

    @bot.slash_command(name="force_update", description="[ADMIN] Força a atualização de todos os registrados agora")
    @discord.default_permissions(administrator=True)
    async def force_update(ctx: discord.ApplicationContext):
        from events import run_auto_update  # local import to avoid circular dependency
        logs_channel = bot.get_channel(LOGS_CHANNEL_ID)
        logs_mention = logs_channel.mention if logs_channel else f"<#{LOGS_CHANNEL_ID}>"
        await ctx.respond(f"🔄 Atualização forçada iniciada! Acompanhe o resultado em {logs_mention}.", ephemeral=True)
        await run_auto_update(bot)

    @bot.slash_command(name="report_salas", description="[ADMIN] Relatório de salas ativas nas categorias monitoradas")
    @discord.default_permissions(administrator=True)
    async def report_salas(ctx: discord.ApplicationContext):
        guild = bot.get_guild(SERVER_ID)
        if not guild:
            await ctx.respond("❌ Servidor não encontrado.", ephemeral=True)
            return

        fuso_brt = timezone(timedelta(hours=-3))
        agora    = datetime.now(fuso_brt).strftime("%d/%m/%Y • %H:%M")

        total_salas   = 0
        total_pessoas = 0
        desc_lines    = []

        for cat_id, cat_name in VOICE_CATEGORY_NAMES.items():
            salas   = 0
            pessoas = 0
            for ch in guild.voice_channels:
                if ch.category_id != cat_id:
                    continue
                if ch.id in VOICE_TRIGGER_MAP:
                    continue
                if ch.id in VOICE_PROTECTED_CHANNELS:
                    # Conta apenas pessoas do lobby da categoria, não a sala em si
                    pessoas += len(ch.members)
                    continue
                salas   += 1
                pessoas += len(ch.members)
            total_salas   += salas
            total_pessoas += pessoas
            desc_lines.append(
                f"**{cat_name}**\nSalas: {salas}\nPessoas: {pessoas}"
            )

        desc = "\n\n".join(desc_lines)
        desc += f"\n\n🔊 **Total de Salas: {total_salas}**\n👥 **Total de Pessoas: {total_pessoas}**"

        embed = discord.Embed(
            title=f"Relatório de Salas | {agora}",
            description=desc,
            color=discord.Color.blue()
        )
        await ctx.respond(embed=embed)

    @bot.slash_command(name="force_sweep", description="[ADMIN] Deleta agora todas as salas de voz vazias")
    @discord.default_permissions(administrator=True)
    async def force_sweep(ctx: discord.ApplicationContext):
        from voice import _temp_voice_channels  # import mutable set from voice module
        await ctx.respond("🧹 Varredura de salas iniciada...", ephemeral=True)
        guild = bot.get_guild(SERVER_ID)
        if not guild:
            await ctx.followup.send("❌ Servidor não encontrado.", ephemeral=True)
            return

        deletados = 0
        for channel in list(guild.voice_channels):
            if not channel.category_id or channel.category_id not in VOICE_TARGET_CATEGORIES:
                continue
            if channel.id in VOICE_PROTECTED_CHANNELS:
                continue
            if channel.id in VOICE_TRIGGER_MAP:
                continue
            if len(channel.members) == 0:
                try:
                    await channel.delete(reason="Varredura manual — sala vazia")
                    _temp_voice_channels.discard(channel.id)
                    deletados += 1
                except discord.Forbidden:
                    print(f"[FORCE-SWEEP] Sem permissão para deletar '{channel.name}'")
                except Exception as e:
                    print(f"[FORCE-SWEEP] Erro ao deletar '{channel.name}': {e}")

        await ctx.followup.send(
            f"✅ Varredura concluída! **{deletados}** sala(s) vazia(s) removida(s).",
            ephemeral=True
        )

    @bot.slash_command(name="force_register", description="[ADMIN] Registra manualmente um usuário pelo Discord ID")
    @discord.default_permissions(administrator=True)
    @discord.option("discord_id", description="ID do Discord do usuário (ex: 186518341920227337)", required=True)
    @discord.option("gamertag", description="ID da EA do usuário", required=True)
    @discord.option("plataforma", description="Plataforma", required=True, choices=["pc", "psn", "xbox"])
    async def force_register(ctx: discord.ApplicationContext, discord_id: str, gamertag: str, plataforma: str):
        await ctx.defer(ephemeral=True)

        try:
            target_id = int(discord_id)
        except ValueError:
            await ctx.respond("❌ Discord ID inválido. Use apenas números.", ephemeral=True)
            return

        guild = bot.get_guild(SERVER_ID)
        if not guild:
            await ctx.respond("❌ Servidor não encontrado.", ephemeral=True)
            return

        member = guild.get_member(target_id)
        if not member:
            await ctx.respond(f"❌ Usuário `{discord_id}` não encontrado no servidor.", ephemeral=True)
            return

        await ctx.respond(
            f"<a:buscabf6:1488347979524997171> Registrando **{gamertag}** ({plataforma}) para {member.mention}...",
            ephemeral=True
        )

        data = await asyncio.to_thread(fetch_stats, gamertag, plataforma)

        if data == "api_error":
            await ctx.followup.send("⚠️ A API de stats está instável. Tente novamente em alguns minutos.", ephemeral=True)
            return
        if data is None:
            await ctx.followup.send(
                f"❌ ID **{gamertag}** não encontrado na plataforma **{plataforma}**.\n"
                f"Verifique o ID da EA.",
                ephemeral=True
            )
            return

        kd_val, human_pct = extract_kd_and_human(data)

        if kd_val == 0.0:
            await ctx.followup.send(
                f"⚠️ **{gamertag}** sem stats no **Redsec** ainda.\n"
                f"O usuário precisa jogar partidas de Redsec antes de ser registrado.",
                ephemeral=True
            )
            return

        users     = load_users()
        old_entry = users.get(str(target_id))
        pid, nid  = await asyncio.to_thread(resolve_player_ids, gamertag)
        entry_fr  = {
            "gamertag":      gamertag,
            "platform":      plataforma,
            "registered_at": datetime.utcnow().isoformat()
        }
        if pid and nid:
            entry_fr["persona_id"] = pid
            entry_fr["nucleus_id"] = nid
        users[str(target_id)] = entry_fr
        save_users(users)

        changes = await apply_roles(member, guild, kd_val, human_pct)

        if changes['suspeita_interno'] not in ["Honesto", "Human% indisponível"]:
            _logs_sus = bot.get_channel(LOGS_CHANNEL_ID)
            if _logs_sus:
                await _logs_sus.send(
                    f"📋 **Force Register** | ⚠️ Suspeita | Admin: {ctx.author.mention}\n"
                    f"Usuário: {member.mention} (ID: {member.id})\n"
                    f"Gamertag: **{gamertag}** ({plataforma}) | ⚠️ Human%: **{human_pct:.2f}%** → **{changes['suspeita_interno']}** | "
                    f"{make_links(gamertag, plataforma, pid, nid)}"
                )

        action = "atualizado" if old_entry else "registrado"

        await ctx.followup.send(
            f"✅ **{member.display_name}** ({member.mention}) **{action}** com sucesso!\n"
            f"Gamertag: **{gamertag}** ({plataforma})\n"
            f"KD Redsec: **{kd_val:.2f}** → Role: **{changes['kd_role']}**\n"
            f"Human%: **{human_pct:.2f}%** → **{changes['suspeita_interno']}**\n"
            f"{make_links(gamertag, plataforma, pid, nid)}",
            ephemeral=True
        )

        logs_ch = bot.get_channel(LOGS_CHANNEL_ID)
        if logs_ch:
            await logs_ch.send(
                f"📋 **Force Register** | Admin: {ctx.author.mention}\n"
                f"Usuário: {member.mention} (`{target_id}`) | Ação: **{action}**\n"
                f"Gamertag: `{gamertag}` | Plataforma: `{plataforma}`\n"
                f"KD: **{kd_val:.2f}** → **{changes['kd_role']}** | "
                f"Human%: **{human_pct:.2f}%** → **{changes['suspeita_interno']}** | "
                f"{make_links(gamertag, plataforma, pid, nid)}"
            )

    @bot.slash_command(name="force_remove", description="[ADMIN] Remove um usuário do registro pelo Discord ID ou gamertag")
    @discord.default_permissions(administrator=True)
    @discord.option("discord_id", description="Discord ID do usuário (deixe em branco para buscar por gamertag)", required=False)
    @discord.option("gamertag", description="Gamertag no banco de dados (deixe em branco para buscar por Discord ID)", required=False)
    async def force_remove(ctx: discord.ApplicationContext, discord_id: str = None, gamertag: str = None):
        if not discord_id and not gamertag:
            await ctx.respond("❌ Informe ao menos um: **discord_id** ou **gamertag**.", ephemeral=True)
            return

        users        = load_users()
        removed_id   = None
        removed_info = None

        if discord_id:
            if discord_id in users:
                removed_id   = discord_id
                removed_info = users[discord_id]
            else:
                await ctx.respond(f"❌ Discord ID `{discord_id}` não encontrado no registro.", ephemeral=True)
                return
        else:
            gamertag_lower = gamertag.lower()
            for uid, info in users.items():
                if info.get('gamertag', '').lower() == gamertag_lower:
                    removed_id   = uid
                    removed_info = info
                    break
            if not removed_id:
                await ctx.respond(f"❌ Gamertag `{gamertag}` não encontrada no registro.", ephemeral=True)
                return

        users.pop(removed_id, None)
        save_users(users)

        gt   = removed_info.get('gamertag', '?')
        plat = removed_info.get('platform', '?')
        reg  = removed_info.get('registered_at', '?')[:10]

        await ctx.respond(
            f"✅ Usuário removido do registro!\n"
            f"Discord: <@{removed_id}> (`{removed_id}`)\n"
            f"Gamertag: `{gt}` | Plataforma: `{plat}` | Registrado em: `{reg}`",
            ephemeral=True
        )

        logs_ch = bot.get_channel(LOGS_CHANNEL_ID)
        if logs_ch:
            await logs_ch.send(
                f"🗑️ **Force Remove** | Admin: {ctx.author.mention}\n"
                f"Usuário: <@{removed_id}> (`{removed_id}`)\n"
                f"Gamertag: `{gt}` | Plataforma: `{plat}` | Registrado em: `{reg}`"
            )

    @bot.slash_command(name="search_player", description="[ADMIN] Busca um jogador cadastrado por Discord ID ou gamertag")
    @discord.default_permissions(administrator=True)
    @discord.option("discord_id", description="Discord ID do usuário", required=False)
    @discord.option("gamertag",   description="Gamertag (ID da EA) cadastrada no banco", required=False)
    async def search_player(ctx: discord.ApplicationContext, discord_id: str = None, gamertag: str = None):
        if not discord_id and not gamertag:
            await ctx.respond("❌ Informe ao menos um: **discord_id** ou **gamertag**.", ephemeral=True)
            return

        users      = load_users()
        found_id   = None
        found_info = None

        if discord_id:
            if discord_id in users:
                found_id   = discord_id
                found_info = users[discord_id]
            else:
                await ctx.respond(f"❌ Discord ID `{discord_id}` não encontrado no registro.", ephemeral=True)
                return
        else:
            for uid, info in users.items():
                if info.get('gamertag', '').lower() == gamertag.lower():
                    found_id   = uid
                    found_info = info
                    break
            if not found_id:
                await ctx.respond(f"❌ Gamertag `{gamertag}` não encontrada no registro.", ephemeral=True)
                return

        gt            = found_info.get('gamertag', '?')
        plat          = found_info.get('platform', 'pc')
        registered_at = found_info.get('registered_at', '')
        persona_id    = found_info.get('persona_id', '')
        nucleus_id    = found_info.get('nucleus_id', '')

        await ctx.defer(ephemeral=True)
        await ctx.respond(
            f"<a:buscabf6:1488347979524997171> Buscando stats de **{gt}** ({plat})...",
            ephemeral=True
        )

        data   = await asyncio.to_thread(fetch_stats, gt, plat)
        guild  = bot.get_guild(SERVER_ID)
        member = guild.get_member(int(found_id)) if guild else None

        if data and data != "api_error":
            embed, kd_val, human_pct = build_stats_embed(data, gt, plat, member, registered_at)
        else:
            embed = discord.Embed(
                description=f"Stats de `{gt}` | `{plat}`\n⚠️ Não foi possível buscar stats da API agora.",
                color=discord.Color.greyple()
            )
            if member and member.display_avatar:
                embed.set_thumbnail(url=member.display_avatar.url)

        # Links sem preview
        api_url = f"<https://api.gametools.network/bf6/stats/?name={gt}&platform={plat}>"
        if persona_id and nucleus_id:
            api_url = f"<https://api.gametools.network/bf6/stats/?playerid={persona_id}&nucleus_id={nucleus_id}&platform={plat}>"
        stats_url = f"<https://gametools.network/stats/{plat}/name/{gt}?game=bf6>"

        reg_fmt = ''
        if registered_at:
            try:
                reg_fmt = datetime.fromisoformat(registered_at).strftime('%d/%m/%Y')
            except Exception:
                reg_fmt = registered_at[:10]

        embed.add_field(name="📅 Cadastrado em", value=reg_fmt or '?',     inline=True)
        embed.add_field(name="🆔 Discord ID",    value=f"`{found_id}`",     inline=True)
        if persona_id:
            embed.add_field(name="🎮 Persona ID", value=f"`{persona_id}`", inline=True)
        embed.add_field(name="🔗 Stats",         value=stats_url,           inline=False)
        embed.add_field(name="📡 API JSON",      value=api_url,             inline=False)

        await ctx.followup.send(embed=embed, ephemeral=True)
