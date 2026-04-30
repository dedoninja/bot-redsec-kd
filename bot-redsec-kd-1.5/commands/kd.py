import asyncio
import discord
from datetime import datetime
from config import (
    BOT_SPAM_CHANNEL_ID, ADM_COMMANDS_CHANNEL_ID,
    LOGS_CHANNEL_ID, RULES_CHANNEL_ID, STAFF_ROLE_ID,
    GIF_EA_ID, GIF_DataShare,
)
from database import load_users, save_users
from api import fetch_stats, resolve_player_ids, make_links
from utils import extract_kd_and_human, extract_kd_by_mode, apply_roles

# ✅ IMPORT CORRETO (sem circular import)
from views.troca import TrocaGametagView
from views.relatar_problema import RelatarProblemaView


def setup_kd(bot: discord.Bot):

    @bot.slash_command(name="kd", description="Busca seu KD no Redsec e atribui role")
    @discord.option("gamertag", description="Seu ID da EA", required=True)
    @discord.option("plataforma", description="Plataforma", required=True, choices=["ea", "psn", "xbox", "steam", "epic"])
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

        # ================== BLOQUEIO DE RE-REGISTRO ==================
        users_data  = load_users()
        disc_id_str = str(ctx.author.id)
        old_entry   = users_data.get(disc_id_str)  # ✅ necessário para action

        if old_entry:
            gamertag_atual = old_entry.get("gamertag","N/A")
            plataforma_atual = old_entry.get("platform","N/A")
            rules_mention = f"<#{RULES_CHANNEL_ID}>"

            await ctx.respond(
                f"ℹ️ {ctx.author.mention} (`{gamertag_atual}` | `{plataforma_atual}`), você já está cadastrado no bot!\n\n"
                f"**Para consultar seus stats**, use o comando `/minha_conta` em {spam_mention}.\n"
                f"**Para consultar stats de outros jogadores**, use o comando `/stats` em {spam_mention}.\n\n"
                f"**Cadastrou a ID errada?** Você pode solicitar a troca clicando no botão `🔄 Solicitar Troca` abaixo.\n"
                f"⚠️ Jogadores que forem pegos usando ID que não são deles estão sujeitos a punições e banimentos conforme as regras do servidor ({rules_mention}).\n\n"
                f"❗**Observação:** Caso você tenha cadastrado a ID errada por engano e solicite a troca, **nenhuma punição será aplicada**. "
                f"Porém, se for denunciado ou identificado o uso indevido de ID, medidas administrativas serão tomadas, podendo gerar **banimento do servidor** ou **limitação do uso do bot**.",
                view=TrocaGametagView(bot),
                ephemeral=True
            )
            return

        # ================== VERIFICAÇÃO DE EA ID DUPLICADA ==================
        # Verifica se a EA ID informada já está cadastrada em outro Discord ID
        ea_id_duplicada = False
        discord_id_dono = None
        for user_id, user_data in users_data.items():
            if user_id != disc_id_str and user_data.get("gamertag", "").lower() == gamertag.lower():
                ea_id_duplicada = True
                discord_id_dono = user_id
                break
        
        if ea_id_duplicada:
            rules_mention = f"<#{RULES_CHANNEL_ID}>"
            await ctx.respond(
                f"⚠️ **A EA ID `{gamertag}` já está cadastrada em outro jogador!**\n\n"
                f"Se você acredita que isso é um engano e essa é realmente a sua ID, "
                f"clique no botão abaixo para relatar o problema à Staff.\n\n"
                f"⚠️ **Atenção:** Usar ID que não é sua é uma violação das regras do servidor ({rules_mention}) "
                f"e pode resultar em **banimento**.",
                view=RelatarProblemaView(bot),
                ephemeral=True
            )
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

        # ================== ACTION CORRETO ==================
        action = "atualizado" if old_entry else "registrado"

        # Salva no JSON
        pid, nid = await asyncio.to_thread(resolve_player_ids, gamertag)
        entry_kd = {
            "gamertag": gamertag,
            "platform": plataforma,
            "registered_at": datetime.utcnow().isoformat()
        }

        if pid and nid:
            entry_kd["persona_id"] = pid
            entry_kd["nucleus_id"] = nid

        users_data[disc_id_str] = entry_kd
        save_users(users_data)

        # Log
        logs_ch = bot.get_channel(LOGS_CHANNEL_ID)
        if logs_ch:
            is_sus_log  = changes['suspeita_interno'] not in ["Honesto", "Human% indisponível"]
            human_label = f"⚠️ Human%: **{human_pct:.2f}%**" if is_sus_log else f"Human%: **{human_pct:.2f}%**"

            await logs_ch.send(
                f"📋 **Registro via /kd** | {ctx.author.mention} (`{ctx.author.id}`) | Ação: **{action}**\n"
                f"Gamertag: `{gamertag}` | Plataforma: `{plataforma}`\n"
                f"KD: **{kd_val:.2f}** → **{changes['kd_role']}** | {human_label} | "
                f"{make_links(gamertag, plataforma, pid, nid)}"
            )

        kd_modos = extract_kd_by_mode(data)

        await ctx.followup.send(
            f"✅ KD **Redsec** atual: **{kd_val:.2f}**\n"
            f"Role atribuída: **{changes['kd_role']}**\n"
            f"KD Squad: **{kd_modos['Squad']:.2f}** | KD Duo: **{kd_modos['Duo']:.2f}** | "
            f"KD Solo: **{kd_modos['Solo']:.2f}** | KD Gauntlet: **{kd_modos['Gauntlet']:.2f}**\n"
            f"Status: **{changes['suspeita_publico']}**\n\n"
            f"✅ Seus dados foram salvos! O bot atualizará sua role automaticamente todo dia às 04:00."
        )