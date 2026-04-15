import discord
import asyncio
from datetime import datetime

from config import BOT_SPAM_CHANNEL_ID, ADM_COMMANDS_CHANNEL_ID
from database import load_top5, save_top5, load_users
from api import fetch_stats, make_session
from utils import extract_kd_by_mode
from config import BASE_STATS_URL

# ================== SETUP ==================

def setup_top5(bot: discord.Bot):

    @bot.slash_command(
        name="top5",
        description="Mostra o Top 5 Redsec do dia (Squad, Duo, Solo ou Gauntlet)"
    )
    @discord.option("categoria", description="Modo do Redsec",
                    choices=["Squad", "Duo", "Solo", "Gauntlet"], default="Squad")
    async def top5_command(ctx: discord.ApplicationContext, categoria: str):
        if ctx.channel_id not in (BOT_SPAM_CHANNEL_ID, ADM_COMMANDS_CHANNEL_ID):
            spam_mention = f"<#{BOT_SPAM_CHANNEL_ID}>"
            await ctx.respond(
                f"⚠️ Por favor, use este comando em {spam_mention}.",
                ephemeral=True
            )
            return

        data = load_top5()
        key = categoria.lower()

        if not data.get(key):
            await ctx.respond(
                f"ℹ️ Ainda não há dados de Top 5 para **Redsec {categoria}** hoje.\n"
                f"O ranking é atualizado automaticamente às 04:00 (BRT).",
                ephemeral=False
            )
            return

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
    top_data = {"squad": [], "duo": [], "solo": [], "gauntlet": []}

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

        except Exception as e:
            print(f"[TOP5] Erro ao processar {gamertag}: {e}")
            continue

    # Ordena e mantém Top 5 de cada categoria
    for cat in top_data:
        top_data[cat] = sorted(top_data[cat], key=lambda x: x["kd"], reverse=True)[:5]

    save_top5(top_data)
    print("[TOP5] top5.json salvo.")

    # Envia embed automático no canal de spam
    spam_channel = bot.get_channel(BOT_SPAM_CHANNEL_ID)
    if spam_channel:
        for categoria in ("Squad", "Duo", "Solo", "Gauntlet"):
            key     = categoria.lower()
            players = top_data.get(key, [])
            if not players:
                continue
            embed = _build_top5_embed(players, categoria)
            await spam_channel.send(embed=embed)

    print("[TOP5] Atualização concluída com sucesso.")

# ================== HELPER: EMBED ==================

def _build_top5_embed(players: list, categoria: str) -> discord.Embed:
    """Monta o embed seguindo o layout exato do print + KD visível"""
    medals = ["🥇", "🥈", "🥉", "🔹", "🔸"]
    emoji_cat = "⭕" if categoria != "Gauntlet" else "🏟️"

    embed = discord.Embed(
        title="🏆 **Top 5 Redsec do Dia**",
        description="Rank atualizado diariamente por volta das 4:00 (BRT).",
        color=0xffac33
    )

    for i, player in enumerate(players):
        medal = medals[i] if i < len(medals) else "▪️"
        mention = f"<@{player['discord_id']}>" if player.get("discord_id") else player["gamertag"]
        kd_val = player.get("kd", 0.0)

        embed.add_field(
            name=f"{emoji_cat} **Redsec {categoria}**",
            value=f"{medal} {mention} (`{player['gamertag']}` | `{player['platform']}`) — **KD {kd_val:.2f}**",
            inline=False
        )

    embed.set_footer(text=f"Atualizado em {datetime.now().strftime('%d/%m/%Y %H:%M')} (BRT)")
    return embed