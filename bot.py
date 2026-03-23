import discord
from discord import Bot
from discord.ext import commands
import requests
import os
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# ================== FLASK DUMMY ==================
from flask import Flask, Response, redirect
from threading import Thread
import requests

app = Flask(__name__)

GITHUB_PAGE_URL = "https://dedoninja.github.io/bot-redsec-kd/"

@app.route('/')
def home():
    try:
        resp = requests.get(GITHUB_PAGE_URL, timeout=10)
        return Response(resp.text, content_type='text/html')
    except Exception as e:
        return f"Erro ao carregar página: {str(e)}"

# FAVICON (resolve o 404)
@app.route('/favicon.ico')
def favicon():
    return redirect("https://cdn.discordapp.com/app-icons/1477325845277184112/6a7d1d2360e2cfcb656f221e6b00f908.png")

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

ROLE_SUSPEITO       = 1483271684722131025
ROLE_SUSPEITO_PLUS  = 1483271744713130147
ROLE_CHEATER        = 1483272069042147389

SUSPEITA_ROLES = [ROLE_SUSPEITO, ROLE_SUSPEITO_PLUS, ROLE_CHEATER]

ADM_CHAT_CHANNEL_ID = 405658596051779584
STAFF_ROLE_ID = 472110979790929922

PLATFORMS = {
    'pc': 'pc',
    'psn': 'psn',
    'xbox': 'xbox'
}

GIF_EA_ID = "https://i.imgur.com/8hmECSV.gif"
GIF_DataShare = "https://i.imgur.com/2Qp2qAI.gif"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = discord.Bot(intents=intents)

@bot.event
async def on_ready():
    print(f'{bot.user} online! Use /kd ou /hc')
    try:
        await bot.sync_commands()
        print('Comandos slash sincronizados com sucesso.')
    except Exception as e:
        print(f'Erro ao sincronizar comandos: {e}')

@bot.slash_command(name="ajuda", description="Mostra como usar o bot")
async def ajuda(ctx: discord.ApplicationContext):
    embed = discord.Embed(
        title="Como usar o bot de KD Redsec",
        description=(
            "Use os comandos slash **/kd** ou **/hc** (mais fáceis!)\n\n"
            "**/kd** → busca seu KD no Redsec e atribui role\n"
            "**/hc** → consulta % de humanidade (possíveis cheaters)\n\n"
            "Selecione a plataforma no menu dropdown (pc, psn ou xbox).\n\n"
            "**Como pegar seu ID da EA?** Veja o GIF abaixo!\n\n"
            "Qualquer dúvida, chama a staff!"
        ),
        color=discord.Color.blue()
    )
    embed.set_image(url=GIF_EA_ID)
    await ctx.respond(embed=embed)

@bot.slash_command(name="kd", description="Busca seu KD no Redsec e atribui role")
@discord.option("gamertag", description="Seu ID da EA", required=True)
@discord.option("plataforma", description="Plataforma", required=True, choices=["pc", "psn", "xbox"],)
async def kd(ctx: discord.ApplicationContext, gamertag: str, plataforma: str):
    await ctx.defer()

    api_platform = plataforma
    base_url = "https://api.gametools.network/bf6/stats/?categories=multiplayer&raw=false&format_values=true&seperation=false&skip_battlelog=true"

    await ctx.respond(f'<a:buscabf6:1485382186902229002> Buscando KD **Redsec** de **{gamertag}** ({plataforma})... *Pode demorar até 1 minuto.*')

    try:
        session = requests.Session()
        retries = Retry(total=1, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        session.mount('https://', HTTPAdapter(max_retries=retries))

        url = f"{base_url}&name={gamertag}&platform={api_platform}"
        resp = session.get(url, timeout=45)

        if resp.status_code != 200:
            await ctx.respond(f'❌ ID **{gamertag}** não encontrado na plataforma **{plataforma}**.\n• Verifique o **ID da EA**.')
            return

        data = resp.json()

        kd = 0.0
        found_mode = False

        for group in data.get('gameModeGroups', []):
            if group.get('gamemodeName') == 'Redsec':
                kd = float(group.get('killDeath', 0.0))
                found_mode = True
                break

        if not found_mode:
            for mode in data.get('gameModes', []):
                if mode.get('gamemodeName') == 'Redsec':
                    kd = float(mode.get('killDeath', 0.0))
                    found_mode = True
                    break

        if not found_mode or kd == 0.0:
            print(f"[DEBUG] Fallback ativado para {gamertag} - buscando personaId/nucleusId")
            player_url = f"https://api.gametools.network/bf6/player?name={gamertag}"
            player_resp = session.get(player_url, timeout=45)

            if player_resp.status_code == 200:
                player_data = player_resp.json()
                persona_id = None
                nucleus_id = None

                print("[DEBUG] Personas encontradas:")
                personas = player_data.get('results', [])
                if not personas:
                    print("[DEBUG] Nenhuma persona encontrada! JSON completo:", player_data)
                for persona in personas:
                    pid = persona.get('platformId')
                    print(f"  - platformId: {pid}, personaId: {persona.get('personaId')}, nucleusId: {persona.get('nucleusId')}")

                for persona in personas:
                    if persona.get('platformId') == 'cem_ea_id':
                        persona_id = persona.get('personaId')
                        nucleus_id = persona.get('nucleusId')
                        print(f"[DEBUG] Prioridade cem_ea_id encontrado: personaId={persona_id}, nucleusId={nucleus_id}")
                        break

                if not persona_id:
                    for persona in personas:
                        pid = persona.get('platformId')
                        if pid in ['steam', 'origin']:
                            persona_id = persona.get('personaId')
                            nucleus_id = persona.get('nucleusId')
                            print(f"[DEBUG] Fallback {pid} encontrado: personaId={persona_id}, nucleusId={nucleus_id}")
                            break

                if persona_id and nucleus_id:
                    fixed_url = f"{base_url}&playerid={persona_id}&nucleus_id={nucleus_id}&platform={api_platform}"
                    resp = session.get(fixed_url, timeout=45)
                    if resp.status_code == 200:
                        data = resp.json()
                        print(f"[DEBUG] Segunda tentativa bem-sucedida com personaId={persona_id}, nucleusId={nucleus_id}")

                        kd = 0.0
                        found_mode = False

                        for group in data.get('gameModeGroups', []):
                            if group.get('gamemodeName') == 'Redsec':
                                kd = float(group.get('killDeath', 0.0))
                                found_mode = True
                                break

                        if not found_mode:
                            for mode in data.get('gameModes', []):
                                if mode.get('gamemodeName') == 'Redsec':
                                    kd = float(mode.get('killDeath', 0.0))
                                    found_mode = True
                                    break

        if not found_mode or kd == 0.0:
            await ctx.respond(
                f'⚠️ **{gamertag}** sem stats no **Redsec** ainda.\n'
                f'• Jogue mais partidas de Redsec.\n'
                f'• Ative "Gameplay Data Sharing" no BF6. Veja como: <{GIF_DataShare}>\n'
                f'• Use o **ID da EA** correto.\n'
                f'• Como pegar seu ID da EA? Veja aqui: {GIF_EA_ID}'
            )
            return

        human_pct_str = data.get('humanPrecentage', '0')
        human_pct = float(human_pct_str.replace('%', ''))

        member = ctx.author
        guild = bot.get_guild(SERVER_ID)

        for role_id in SUSPEITA_ROLES:
            role = guild.get_role(role_id)
            if role and role in member.roles:
                await member.remove_roles(role)

        suspeita_role = None
        suspeita_nome = "Honesto"

        if human_pct == 0.0:
            suspeita_nome = "Human% não disponível ou perfil sem dados suficientes (0.00%)"

        elif human_pct >= 70.0:
            suspeita_nome = "Honesto"

        elif human_pct >= 50.0:
            suspeita_role = guild.get_role(ROLE_SUSPEITO)
            suspeita_nome = "Sus 50-70%"

        elif human_pct >= 30.0:
            suspeita_role = guild.get_role(ROLE_SUSPEITO_PLUS)
            suspeita_nome = "Sus 30-50%"

        else:
            suspeita_role = guild.get_role(ROLE_CHEATER)
            suspeita_nome = "Cheater 0-30%"

        if suspeita_role:
            await member.add_roles(suspeita_role)

            adm_channel = bot.get_channel(ADM_CHAT_CHANNEL_ID)
            if adm_channel:
                staff_role = guild.get_role(STAFF_ROLE_ID)
                if staff_role:
                    await adm_channel.send(
                        f"{staff_role.mention} Suspeita detectada:\n"
                        f"Usuário: {member.mention} (ID: {member.id})\n"
                        f"Gamertag: **{gamertag}**\n"
                        f"Human%: **{human_pct:.2f}%** → **{suspeita_nome}**"
                    )

        if kd == 0.0:
            await ctx.respond(
                f'⚠️ **{gamertag}** sem stats no **Redsec** ainda.\n'
                f'• Jogue mais partidas de Redsec.\n'
                f'• Ative "Gameplay Data Sharing" no BF6. Veja como: <{GIF_DataShare}>\n'
                f'• Use o **ID da EA** correto.\n'
                f'• Como pegar seu ID da EA? Veja aqui: {GIF_EA_ID}'
            )
            return

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
            await ctx.respond(f'📉 KD **{kd:.2f}** no Redsec (abaixo de 2.0). Nenhuma role atribuída.')
            return

        new_role = guild.get_role(new_role_id)
        if not new_role:
            await ctx.respond('❌ Erro interno: role não encontrada. Contate a staff!')
            return

        await member.add_roles(new_role)

        await ctx.respond(
            f'✅ KD **Redsec** atual: **{kd:.2f}**\n'
            f'Role atribuída: **{role_name}**\n'
            f'Você já pode criar ou entrar salas restritas ao seu KD. 🔥'
        )

    except Exception as e:
        await ctx.respond(f'❌ Erro ao buscar stats: {str(e)}\nTente novamente em alguns minutos.')

@bot.slash_command(name="hc", description="Consulta % de humanidade (possíveis cheaters)")
@discord.option("gamertag", description="ID da EA", required=True)
@discord.option("plataforma", description="Plataforma", required=True, choices=["pc", "psn", "xbox"])
async def hc(ctx: discord.ApplicationContext, gamertag: str, plataforma: str):
    await ctx.defer()

    api_platform = plataforma
    base_url = "https://api.gametools.network/bf6/stats/?categories=multiplayer&raw=false&format_values=true&seperation=false&skip_battlelog=true"

    await ctx.respond(f'<a:buscabf6:1485382186902229002> Consultando human% de **{gamertag}** ({plataforma})... *Pode demorar até 1 minuto.*')

    try:
        session = requests.Session()
        retries = Retry(total=1, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        session.mount('https://', HTTPAdapter(max_retries=retries))

        url = f"{base_url}&name={gamertag}&platform={api_platform}"
        resp = session.get(url, timeout=45)

        if resp.status_code != 200:
            await ctx.respond(f'❌ ID **{gamertag}** não encontrado na plataforma **{plataforma}**.\n• Verifique o **ID da EA**.')
            return

        data = resp.json()

        human_pct_str = data.get('humanPrecentage', '0')
        human_pct = float(human_pct_str.replace('%', ''))

        if human_pct == 0.0:
            print(f"[DEBUG] Fallback ativado no /hc para {gamertag}")
            player_url = f"https://api.gametools.network/bf6/player?name={gamertag}"
            player_resp = session.get(player_url, timeout=45)

            if player_resp.status_code == 200:
                player_data = player_resp.json()
                persona_id = None
                nucleus_id = None

                personas = player_data.get('results', [])
                if not personas:
                    print("[DEBUG] Nenhuma persona encontrada no /hc! JSON:", player_data)

                for persona in personas:
                    if persona.get('platformId') == 'cem_ea_id':
                        persona_id = persona.get('personaId')
                        nucleus_id = persona.get('nucleusId')
                        print(f"[DEBUG] Prioridade cem_ea_id no /hc: personaId={persona_id}, nucleusId={nucleus_id}")
                        break

                if not persona_id:
                    for persona in personas:
                        pid = persona.get('platformId')
                        if pid in ['steam', 'origin']:
                            persona_id = persona.get('personaId')
                            nucleus_id = persona.get('nucleusId')
                            print(f"[DEBUG] Fallback {pid} no /hc: personaId={persona_id}, nucleusId={nucleus_id}")
                            break

                if persona_id and nucleus_id:
                    fixed_url = f"{base_url}&playerid={persona_id}&nucleus_id={nucleus_id}&platform={api_platform}"
                    resp = session.get(fixed_url, timeout=45)
                    if resp.status_code == 200:
                        data = resp.json()
                        print(f"[DEBUG] Segunda tentativa bem-sucedida no /hc")

                        human_pct_str = data.get('humanPrecentage', '0')
                        human_pct = float(human_pct_str.replace('%', ''))

        float(human_pct_str.replace('%', '').strip())

        if human_pct == 0.0:
            categoria = "Human% não disponível ou perfil sem dados suficientes (0.00%)"
        elif human_pct >= 70.0:
            categoria = "Jogador Normal ✅"
        elif human_pct >= 50.0:
            categoria = "Suspeito 🚨"
        elif human_pct >= 30.0:
            categoria = "Possível Cheater ⚠️"
        else:
            categoria = "Cheater 💀"

        await ctx.respond(f'Human% de **{gamertag}**: **{human_pct:.2f}%** → **{categoria}**')

    except Exception as e:
        await ctx.respond(f'❌ Erro ao consultar human%: {str(e)}\nVerifique o ID da EA.')

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("Comando desconhecido. Use `/ajuda`.")
    else:
        print(f"Erro: {error}")

bot.run(TOKEN)