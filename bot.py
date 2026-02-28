import discord
from discord.ext import commands
import requests
import os

# ==================== CONFIGS ====================
TOKEN = os.getenv('TOKEN')  # O token vem da variável de ambiente (Render)

SERVER_ID = 405506950562840577

ROLE_KD2 = 1477322781774450868
ROLE_KD3 = 1477322769825005599
ROLE_KD4 = 1477322732201971945
ROLE_KD5 = 1477322675612553296

KD_ROLES = [ROLE_KD2, ROLE_KD3, ROLE_KD4, ROLE_KD5]

PLATFORMS = {
    'pc': 'pc',
    'steam': 'pc',
    'psn': 'psn',
    'xbox': 'xbox'
}
# ================================================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)
bot.remove_command('help')

@bot.event
async def on_ready():
    print(f'{bot.user} online! Use !kd <gamertag> <plataforma>')

@bot.command(name='ajuda', aliases=['help'])
async def ajuda(ctx):
    embed = discord.Embed(
        title="Como usar o bot de KD Redsec Squad",
        description="Comando: `!kd <seu gamertag> <plataforma>`\n\n**Plataformas válidas:**\n- `pc` ou `steam` (PC)\n- `psn` (PlayStation)\n- `xbox` (Xbox)\n\n**Exemplo genérico:**\n`!kd SeuNick pc`\n\nO bot busca seu KD no modo **Redsec Squad** e atribui a role correspondente automaticamente.\n\nQualquer dúvida, chama a staff!",
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed)

@bot.command(name='kd')
async def assign_kd(ctx, gamertag: str, platform: str):
    platform = platform.lower()
    if platform not in PLATFORMS:
        await ctx.send('❌ Plataforma inválida! Use: **pc**, **steam**, **psn** ou **xbox**.\nExemplo: `!kd SeuNick pc`')
        return

    api_platform = PLATFORMS[platform]
    url = f"https://api.gametools.network/bf6/stats/?categories=multiplayer&raw=false&format_values=true&seperation=false&name={gamertag}&platform={api_platform}&skip_battlelog=true"

    await ctx.send(f'🔍 Buscando KD **Redsec Squad** de **{gamertag}** ({platform})...')

    try:
        resp = requests.get(url, timeout=15).json()
        kd = 0.0

        for mode in resp.get('gameModes', []):
            if mode.get('gamemodeName') == 'Redsec Squad':
                kd = float(mode.get('killDeath', 0.0))
                break

        if kd == 0.0:
            await ctx.send(f'⚠️ **{gamertag}** sem stats no **Redsec Squad** ainda.\n• Jogue mais partidas BR Squads\n• Ative "Gameplay Data Sharing" no BF6')
            return

        member = ctx.author
        guild = bot.get_guild(SERVER_ID)
        for role_id in KD_ROLES:
            role = guild.get_role(role_id)
            if role and role in member.roles:
                await member.remove_roles(role)

        if 2.0 <= kd < 3.0:
            new_role_id = ROLE_KD2
            role_name = 'Redsec KD2'
        elif 3.0 <= kd < 4.0:
            new_role_id = ROLE_KD3
            role_name = 'Redsec KD3'
        elif 4.0 <= kd < 5.0:
            new_role_id = ROLE_KD4
            role_name = 'Redsec KD4'
        elif kd >= 5.0:
            new_role_id = ROLE_KD5
            role_name = 'Redsec KD5+'
        else:
            await ctx.send(f'📉 KD **{kd:.2f}** no Redsec Squad (abaixo de 2.0). Nenhuma role atribuída.')
            return

        new_role = guild.get_role(new_role_id)
        if not new_role:
            await ctx.send('❌ Erro interno: role não encontrada. Contate a staff!')
            return

        await member.add_roles(new_role)

        await ctx.send(
            f'✅ KD **Redsec Squad** atual: **{kd:.2f}**\n'
            f'Role atribuída: **{role_name}**\n'
            f'Você já pode criar ou entrar salas restritas ao seu KD. 🔥'
        )

    except Exception as e:
        await ctx.send(f'❌ Erro ao buscar stats: {str(e)}\nVerifique gamertag/plataforma ou contate a **staff** do servidor.')

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        comando_digitado = ctx.invoked_with
        await ctx.send(
            f"Comando `{ctx.prefix}{comando_digitado}` desconhecido ou digitado errado. "
            f"Use `!ajuda` para ver como usar."
        )
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(
            f"Faltou argumentos no comando `{ctx.prefix}{ctx.invoked_with}`. "
            f"Use `!ajuda` para ver o formato correto."
        )
    else:
        print(f"Erro não tratado: {error}")

bot.run(TOKEN)