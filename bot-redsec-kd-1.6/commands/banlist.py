import discord
import json
import os
from datetime import datetime

from config import BANS_FILE, BAN_TYPES, ADM_COMMANDS_CHANNEL_ID, LOGS_CHANNEL_ID


def load_bans() -> dict:
    os.makedirs(os.path.dirname(BANS_FILE), exist_ok=True)
    if not os.path.exists(BANS_FILE):
        return {}
    try:
        with open(BANS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[BANLIST] Erro ao carregar bans.json: {e}")
        return {}


def save_bans(bans: dict):
    os.makedirs(os.path.dirname(BANS_FILE), exist_ok=True)
    with open(BANS_FILE, "w", encoding="utf-8") as f:
        json.dump(bans, f, ensure_ascii=False, indent=2)


def is_banned(user_id: int, ban_type: str) -> bool:
    """Verifica se o usuário está banido de um tipo específico"""
    bans = load_bans()
    user_str = str(user_id)
    if user_str not in bans:
        return False
    return ban_type in bans[user_str].get("types", [])


def get_ban_reason(user_id: int, ban_type: str) -> str:
    """Retorna o motivo do ban (usado em mensagens de erro)"""
    bans = load_bans()
    user_str = str(user_id)
    if user_str in bans and ban_type in bans[user_str].get("motivos", {}):
        return bans[user_str]["motivos"][ban_type]
    return "Sem motivo registrado"


def setup_banlist(bot: discord.Bot):

    @bot.slash_command(name="ban", description="[ADMIN] Bane um usuário de funcionalidades do bot")
    @discord.default_permissions(administrator=True)
    @discord.option("user", description="Usuário a ser banido", required=True)
    @discord.option("tipo", description="Tipo de ban", choices=list(BAN_TYPES.keys()), required=True)
    @discord.option("motivo", description="Motivo do ban (opcional)", required=False)
    async def ban_user(ctx: discord.ApplicationContext, user: discord.Member, tipo: str, motivo: str = None):
        bans = load_bans()
        user_str = str(user.id)

        if user_str not in bans:
            bans[user_str] = {"types": [], "motivos": {}, "banned_at": datetime.utcnow().isoformat()}

        if tipo not in bans[user_str]["types"]:
            bans[user_str]["types"].append(tipo)
            bans[user_str]["motivos"][tipo] = motivo or "Sem motivo informado"

        save_bans(bans)

        await ctx.respond(
            f"✅ **{user.mention}** foi banido do tipo **{tipo}** ({BAN_TYPES.get(tipo, tipo)}).",
            ephemeral=False
        )

        logs_ch = bot.get_channel(LOGS_CHANNEL_ID)
        if logs_ch:
            await logs_ch.send(
                f"🔨 **Ban aplicado** | Admin: {ctx.author.mention}\n"
                f"Usuário: {user.mention} (`{user.id}`)\n"
                f"Tipo: **{tipo}** — {BAN_TYPES.get(tipo, tipo)}\n"
                f"Motivo: {motivo or 'Não informado'}"
            )


    @bot.slash_command(name="unban", description="[ADMIN] Remove ban de um usuário")
    @discord.default_permissions(administrator=True)
    @discord.option("user", description="Usuário a ser desbanido", required=True)
    @discord.option("tipo", description="Tipo de ban a remover", choices=["voice", "register", "commands", "all"], required=True)
    async def unban_user(ctx: discord.ApplicationContext, user: discord.Member, tipo: str):
        bans = load_bans()
        user_str = str(user.id)

        if user_str not in bans:
            await ctx.respond(f"❌ Usuário não está banido.", ephemeral=True)
            return

        if tipo == "all":
            del bans[user_str]
            msg = "todos os tipos"
        elif tipo in bans[user_str].get("types", []):
            bans[user_str]["types"].remove(tipo)
            if not bans[user_str]["types"]:
                del bans[user_str]
            msg = f"tipo **{tipo}**"
        else:
            await ctx.respond(f"❌ Usuário não está banido do tipo **{tipo}**.", ephemeral=True)
            return

        save_bans(bans)

        await ctx.respond(f"✅ Ban removido de **{user.mention}** ({msg}).", ephemeral=False)

        logs_ch = bot.get_channel(LOGS_CHANNEL_ID)
        if logs_ch:
            await logs_ch.send(f"🔓 **Ban removido** | {ctx.author.mention} removeu {msg} de {user.mention}")


    @bot.slash_command(name="banlist", description="[ADMIN] Mostra todos os usuários banidos")
    @discord.default_permissions(administrator=True)
    async def banlist(ctx: discord.ApplicationContext):
        bans = load_bans()
        if not bans:
            await ctx.respond("✅ Não há usuários banidos no momento.", ephemeral=False)
            return

        embed = discord.Embed(title="🔨 Banlist Atual", color=0xff0000)
        for user_id, data in bans.items():
            types_str = ", ".join([BAN_TYPES.get(t, t) for t in data.get("types", [])])
            embed.add_field(
                name=f"Usuário",
                value=f"<@{user_id}> (`{user_id}`)\nTipos: **{types_str}**\nBanido em: {data.get('banned_at', 'Desconhecido')[:10]}",
                inline=False
            )
        await ctx.respond(embed=embed, ephemeral=False)