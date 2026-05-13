import discord
import asyncio
from datetime import datetime

from config import BOT_SPAM_CHANNEL_ID, ADM_COMMANDS_CHANNEL_ID
from database import load_top5, save_top5, load_users
from api import fetch_stats, make_session
from utils import extract_kd_by_mode, extract_infantry_kd
from config import BASE_STATS_URL

# ================== SETUP ==================

def setup_top5(bot: discord.Bot):

    @bot.slash_command(
        name="top5",
        description="Mostra o Top 5 Redsec do dia (Squad, Duo, Solo, Gauntlet ou KD de Infantaria)"
    )
    @discord.option("categoria", description="Modo",
                    choices=["Squad", "Duo", "Solo", "Gauntlet", "KD de Infantaria"], default="Squad")
    async def top5_command(ctx: discord.ApplicationContext, categoria: str):

        # Verificação de ban
        from commands.banlist import is_banned, get_ban_reason
        if is_banned(ctx.author.id, "commands"):
            motivo = get_ban_reason(ctx.author.id, "commands")
            await ctx.respond(f"❌ Você está banido de usar comandos.\nMotivo: {motivo}", ephemeral=True)
            return
        
        if ctx.channel_id not in (BOT_SPAM_CHANNEL_ID, ADM_COMMANDS_CHANNEL_ID):
            spam_mention = f"<#{BOT_SPAM_CHANNEL_ID}>"
            await ctx.respond(
                f"⚠️ Por favor, use este comando em {spam_mention}.",
                ephemeral=True
            )
            return

        data = load_top5()
        key = "infantryKD" if categoria == "KD de Infantaria" else categoria.lower()

        if not data.get(key):
            nome_exibido = "KD de Infantaria" if categoria == "KD de Infantaria" else f"Redsec {categoria}"
            await ctx.respond(
                f"ℹ️ Ainda não há dados de Top 5 para **{nome_exibido}** hoje.\n"
                f"O ranking é atualizado automaticamente às 04:00 (BRT).",
                ephemeral=False
            )
            return

        if categoria == "KD de Infantaria":
            embed = _build_top5_infantry_embed(data[key])
        else:
            embed = _build_top5_embed(data[key], categoria)
        await ctx.respond(embed=embed)

    # Comando temporário para forçar atualização do Top 5 (apenas admin)
    @bot.slash_command(
        name="force_top5",
        description="[ADMIN] Força a atualização do Top 5 agora"
    )
    @discord.default_permissions(administrator=True)
    async def force_top5(ctx: discord.ApplicationContext):
        await ctx.respond("🔄 Forçando atualização do Top 5 agora...", ephemeral=True)
        await update_daily_top5(bot)
        await ctx.followup.send("✅ Top 5 atualizado com sucesso! Use `/top5` para ver o resultado.", ephemeral=True)

    # Expõe a função de atualização para ser chamada por events.py
    bot.top5_update = update_daily_top5

# ================== ATUALIZAÇÃO DIÁRIA ==================

async def update_daily_top5(bot: discord.Bot):
    """
    Chamada pelo events.py após o auto_update das 04:00.
    Varre todos os usuários cadastrados, extrai KD por modo e
    salva o Top 5 de cada categoria em top5.json.
    Depois envia o embed de ranking no canal de spam.
    """
    print("[TOP5] Iniciando atualização diária do Top 5...")

    users    = load_users()
    top_data = {"squad": [], "duo": [], "solo": [], "gauntlet": [], "infantryKD": []}

    for disc_id, user_info in users.items():
        gamertag   = user_info.get("gamertag")
        platform   = user_info.get("platform")
        persona_id = user_info.get("persona_id")
        nucleus_id = user_info.get("nucleus_id")

        if not gamertag or not platform:
            continue

        try:
            # Usa persona_id/nucleus_id se disponível, senão busca por nome
            if persona_id and nucleus_id:
                url     = (
                    f"{BASE_STATS_URL}"
                    f"&playerid={persona_id}&nucleus_id={nucleus_id}&platform={platform}"
                )
                session = make_session()
                resp    = await asyncio.to_thread(session.get, url, timeout=15)
                data    = resp.json() if resp.status_code == 200 else None
            else:
                data = await asyncio.to_thread(fetch_stats, gamertag, platform)

            if not data or data == "api_error":
                continue

            kd_modos = extract_kd_by_mode(data)

            entry_base = {
                "discord_id": disc_id,
                "gamertag":   gamertag,
                "platform":   platform,
            }

            top_data["squad"].append({**entry_base,   "kd": kd_modos["Squad"]})
            top_data["duo"].append({**entry_base,     "kd": kd_modos["Duo"]})
            top_data["solo"].append({**entry_base,    "kd": kd_modos["Solo"]})
            top_data["gauntlet"].append({**entry_base,"kd": kd_modos["Gauntlet"]})

            # KD de Infantaria
            kd_infantry = extract_infantry_kd(data)
            top_data["infantryKD"].append({**entry_base, "kd": kd_infantry})

        except Exception as e:
            print(f"[TOP5] Erro ao processar {gamertag}: {e}")
            continue

    # Ordena e mantém Top 5 de cada categoria
    for cat in top_data:
        top_data[cat] = sorted(top_data[cat], key=lambda x: float(x.get("kd", 0) or 0), reverse=True)[:5]

    save_top5(top_data)
    print("[TOP5] top5.json salvo.")
    print("[TOP5] Atualização concluída com sucesso.")

# ================== HELPER: EMBED ==================

def _build_top5_embed(players: list, categoria: str) -> discord.Embed:
    """Monta o embed de Top 5 para uma categoria — categoria aparece uma vez no título."""
    medals    = ["🥇", "🥈", "🥉", "🔹", "🔸"]
    emoji_cat = "⭕" if categoria != "Gauntlet" else "🏟️"
    color     = 0xd2cfd4 if categoria == "Gauntlet" else 0xf92f60

    embed = discord.Embed(
        title=f"🏆 Top 5 Redsec {categoria} do Dia",
        description=f"{emoji_cat} Rank atualizado diariamente às 04:00 (BRT).",
        color=color
    )

    for i, player in enumerate(players):
        medal   = medals[i] if i < len(medals) else "▪️"
        mention = f"<@{player['discord_id']}>" if player.get("discord_id") else player["gamertag"]
        kd_val  = player.get("kd", 0.0)
        embed.add_field(
            name=f"{medal} #{i+1}",
            value=f"{mention} (`{player['gamertag']}` | `{player['platform']}`) | KD: **{kd_val:.2f}**",
            inline=False
        )

    embed.set_footer(text=f"Atualizado em {datetime.now().strftime('%d/%m/%Y %H:%M')} (BRT)")
    return embed

# ================== HELPER: EMBED INFANTRY KD ==================

def _build_top5_infantry_embed(players: list) -> discord.Embed:
    """Monta o embed de Top 5 Infantry KD"""
    medals = ["🥇", "🥈", "🥉", "🔹", "🔸"]

    embed = discord.Embed(
        title="🏆 Top 5 KD de Infantaria do Dia",
        description="🔫 Rank atualizado diariamente às 04:00 (BRT).",
        color=0x50be4a
    )

    for i, player in enumerate(players):
        medal   = medals[i] if i < len(medals) else "▪️"
        mention = f"<@{player['discord_id']}>" if player.get("discord_id") else player["gamertag"]
        kd_val  = player.get("kd", 0.0)
        embed.add_field(
            name=f"{medal} #{i+1}",
            value=f"{mention} (`{player['gamertag']}` | `{player['platform']}`) | iKD: **{kd_val:.2f}**",
            inline=False
        )

    embed.set_footer(text=f"Atualizado em {datetime.now().strftime('%d/%m/%Y %H:%M')} (BRT)")
    return embed