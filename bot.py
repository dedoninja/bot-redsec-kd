import discord
from discord.ext import commands
import requests
import os
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# ================== FLASK DUMMY ==================
from flask import Flask
from threading import Thread

# Servidor dummy para o Fly.io (porta 8080)
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot Redsec Squad online! Tudo certo."

def run_flask():
    app.run(host='0.0.0.0', port=8080)

Thread(target=run_flask, daemon=True).start()

# ==================== CONFIGS ====================
TOKEN = os.getenv('TOKEN')  # Token do ambiente (Fly.io)

SERVER_ID = 405506950562840577

ROLE_KD2 = 1477322781774450868
ROLE_KD3 = 1477322769825005599
ROLE_KD4 = 1477322732201971945
ROLE_KD5 = 1477322675612553296

KD_ROLES = [ROLE_KD2, ROLE_KD3, ROLE_KD4, ROLE_KD5]

PLATFORMS = {
    'pc': 'pc',
    'psn': 'psn',
    'xbox': 'xbox'
}
# ================================================

GIF_EA_ID = "https://i.imgur.com/8hmECSV.gif"  # GIF explicando como pegar o ID da EA
GIF_DataShare = "https://i.imgur.com/2Qp2qAI.gif"  # GIF como habilitar o Data Share

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents, case_insensitive=True)
bot.remove_command('help')

@bot.event
async def on_ready():
    print(f'{bot.user} online! Use !kd <seu ID EA/Origin> pc')

@bot.command(name='ajuda', aliases=['help'])
async def ajuda(ctx):
    embed = discord.Embed(
        title="Como usar o bot de KD Redsec Squad",
        description=(
            "Comando: `!kd <seu ID EA/Origin> pc`\n\n"
            "**Plataformas válidas:**\n"
            "- `pc` (Steam ou launcher EA)\n"
            "- `psn` (PlayStation)\n"
            "- `xbox` (Xbox)\n\n"
            "**Exemplo:**\n"
            "`!kd SeuID pc`\n\n"
            "O bot busca seu KD no modo **Redsec Squad** e atribui a role correspondente automaticamente.\n\n"
            "**Como pegar seu ID da EA/Origin no GIF abaixo.**\n\n"
            "Qualquer dúvida, chama a staff!"
        ),
        color=discord.Color.blue()
    )
    embed.set_image(url=GIF_EA_ID)  # Embeda o GIF como imagem principal
    await ctx.send(embed=embed)

@bot.command(name='kd')
async def assign_kd(ctx, gamertag: str, platform: str):
    platform = platform.lower()
    if platform not in PLATFORMS:
        await ctx.send(
            '❌ Plataforma inválida! Use apenas: **pc**, **psn** ou **xbox**.\n'
            f'Exemplo: `!kd SeuID pc`\n'
            f'• Use sempre o **ID da EA/Origin** (mesmo se jogar no Steam).\n'
            f'• Como pegar seu ID da EA: {GIF_EA_ID}'
        )
        return

    api_platform = PLATFORMS[platform]
    url = f"https://api.gametools.network/bf6/stats/?categories=multiplayer&raw=false&format_values=true&seperation=false&name={gamertag}&platform={api_platform}&skip_battlelog=true"

    await ctx.send(f'🔍 Buscando KD **Redsec Squad** de **{gamertag}** ({platform})...')

    try:
        session = requests.Session()
        retries = Retry(total=1, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        session.mount('https://', HTTPAdapter(max_retries=retries))

        resp = session.get(url, timeout=45)

        if resp.status_code != 200:
            if resp.status_code == 404:
                await ctx.send(
                    f'❌ ID **{gamertag}** não encontrado na plataforma **{platform}**.\n'
                    f'• Verifique se digitou o **ID da EA/Origin** exatamente (mesmo se jogar no Steam).\n'
                    f'• Perfil privado ou sem stats no Redsec Squad. Como deixar seu perfil público: <{GIF_DataShare}>\n'
                    f'• Como pegar seu ID da EA: {GIF_EA_ID}\n'
                    f'• Contate a staff se persistir.'
                )
            elif resp.status_code == 429:
                await ctx.send('❌ API sobrecarregada (rate limit). Tente novamente em 1 minuto.')
            else:
                await ctx.send(f'❌ Erro na API: Status {resp.status_code}. Tente novamente ou contate a staff.')
            return

        data = resp.json()
        kd = 0.0

        for mode in data.get('gameModes', []):
            if mode.get('gamemodeName') == 'Redsec Squad':
                kd = float(mode.get('killDeath', 0.0))
                break

        if kd == 0.0:
            await ctx.send(
                f'⚠️ **{gamertag}** sem stats no **Redsec Squad** ainda.\n'
                f'• Jogue mais partidas BR Squads.\n'
                f'• Ative "Gameplay Data Sharing" no BF6: <{GIF_DataShare}>\n'
                f'• Use o **ID da EA/Origin** correto (mesmo no Steam).\n'
                f'• Como pegar seu ID da EA: {GIF_EA_ID}'
            )
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

    except requests.exceptions.Timeout:
        await ctx.send('❌ Demora de resposta do servidor de estatísticas da EA (API). Tente novamente em alguns minutos.\n• Possível sobrecarga temporária no API.')
    except requests.exceptions.JSONDecodeError:
        await ctx.send('❌ Resposta da API inválida (não é JSON). Possível "404 Not Found" ou "Internal Server Error" no servidor de estatísticas (API).\n• Tente novamente em alguns minutos pois pode ser sobrecarga temporária no API.\n• Verifique se o ID da EA/Origin está correto e o perfil está público.\n• Jogue algumas partidas se você acabou de mudar o perfil para público.\n• Como pegar seu ID da EA: {GIF_EA_ID}')
    except Exception as e:
        await ctx.send(f'❌ Erro ao buscar stats: {str(e)}\nVerifique o ID da EA/Origin e plataforma.\n• Use o **ID da EA/Origin** correto (mesmo se jogar no Steam).\n• Contate a staff se persistir.')

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