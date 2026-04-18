import discord
from datetime import datetime
from collections import defaultdict

from config import ADM_COMMANDS_CHANNEL_ID, LOGS_CHANNEL_ID
from database import load_users


def setup_duplicados(bot: discord.Bot):

    @bot.slash_command(
        name="duplicados",
        description="[ADMIN] Lista gamertags que estão sendo usadas por mais de uma pessoa"
    )
    @discord.default_permissions(administrator=True)
    async def check_duplicados(ctx: discord.ApplicationContext):
        await ctx.defer(ephemeral=True)

        users = load_users()
        if not users:
            await ctx.followup.send("❌ Nenhum usuário cadastrado.", ephemeral=True)
            return

        # Agrupa por gamertag (case insensitive)
        gamertag_map = defaultdict(list)

        for disc_id, info in users.items():
            gamertag = info.get("gamertag", "").strip().lower()
            if gamertag:
                gamertag_map[gamertag].append({
                    "discord_id": disc_id,
                    "gamertag_real": info.get("gamertag"),
                    "platform": info.get("platform", "?"),
                    "registered_at": info.get("registered_at")
                })

        # Filtra apenas duplicatas
        duplicates = {gt: data for gt, data in gamertag_map.items() if len(data) > 1}

        if not duplicates:
            await ctx.followup.send("✅ Nenhuma gamertag duplicada encontrada no momento.", ephemeral=False)
            return

        embed = discord.Embed(
            title="🔍 Gamertags Duplicadas Encontradas",
            description="Ordenado por data de cadastro (mais antigo primeiro)",
            color=0xff0000
        )

        for gamertag_lower, entries in duplicates.items():
            # Ordena por data de registro (mais antigo primeiro)
            sorted_entries = sorted(
                entries,
                key=lambda x: x.get("registered_at", "") or "9999"
            )

            lines = []
            for entry in sorted_entries:
                reg_date = "?"
                if entry.get("registered_at"):
                    try:
                        reg_date = datetime.fromisoformat(entry["registered_at"]).strftime("%d/%m/%Y")
                    except:
                        pass
                lines.append(f"<@{entry['discord_id']}> | `{entry['gamertag_real']}` | `{entry['platform']}` | {reg_date}")

            embed.add_field(
                name=f"🎯 `{gamertag_lower}` — **{len(entries)} usos**",
                value="\n".join(lines),
                inline=False
            )

        await ctx.followup.send(embed=embed, ephemeral=False)

        # Log no canal de logs
        logs_ch = bot.get_channel(LOGS_CHANNEL_ID)
        if logs_ch:
            await logs_ch.send(
                f"🔍 **Verificação de duplicatas** realizada por {ctx.author.mention}\n"
                f"Encontradas **{len(duplicates)}** gamertags duplicadas."
            )