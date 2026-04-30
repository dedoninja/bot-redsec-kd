import discord
from config import SERVER_ID, SUSPEITA_ROLES, ROLE_FAZENDEIRO
from database import load_users
from api import make_links


def setup_suspeitos(bot: discord.Bot):

    @bot.slash_command(name="suspeitos", description="[ADMIN] Lista jogadores com role de suspeita (exceto Fazendeiros)")
    @discord.default_permissions(administrator=True)
    async def suspeitos(ctx: discord.ApplicationContext):
        guild = bot.get_guild(SERVER_ID)
        if not guild:
            await ctx.respond("❌ Servidor não encontrado.", ephemeral=True)
            return

        fazendeiro_role = guild.get_role(ROLE_FAZENDEIRO)
        linhas = []

        for role_id in SUSPEITA_ROLES:
            role = guild.get_role(role_id)
            if not role:
                continue
            for member in role.members:
                # Pula Fazendeiros
                if fazendeiro_role and fazendeiro_role in member.roles:
                    continue
                # Busca gamertag no JSON
                users  = load_users()
                gt     = '?'
                plat   = '?'
                reg_at = '?'
                info   = {}
                for uid, info in users.items():
                    if uid == str(member.id):
                        gt     = info.get('gamertag', '?')
                        plat   = info.get('platform', '?')
                        reg_at = info.get('registered_at', '?')[:10]
                        break
                else:
                    info = {}
                sus_pid = info.get('persona_id') if info.get('gamertag') else None
                sus_nid = info.get('nucleus_id') if info.get('gamertag') else None
                linhas.append(
                    f"- {member.mention} (`{gt}` | {plat}) | Role: **{role.name}** | "
                    f"Cadastrado: {reg_at} | {make_links(gt, plat, sus_pid, sus_nid)}"
                )

        if not linhas:
            await ctx.respond("✅ Nenhum jogador suspeito encontrado (excluindo Fazendeiros).", ephemeral=True)
            return

        # Envia em blocos para não estourar limite
        header = f"🚨 **Jogadores suspeitos ({len(linhas)}) — excluindo Fazendeiros:**\n"
        msg    = header
        msgs   = []
        for linha in linhas:
            if len(msg) + len(linha) + 1 > 1900:
                msgs.append(msg)
                msg = ""
            msg += linha + "\n"
        if msg:
            msgs.append(msg)

        await ctx.respond(msgs[0], ephemeral=False)
        for m in msgs[1:]:
            await ctx.followup.send(m, ephemeral=False)
