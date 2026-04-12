import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, InputText
import requests
import os
import json
import asyncio
import time
from datetime import datetime, timezone, timedelta
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# ================== FLASK DUMMY ==================
from flask import Flask, redirect
from threading import Thread

app = Flask(__name__)

GITHUB_PAGE_URL = "https://dedoninja.github.io/bot-redsec-kd/"

@app.route('/')
def home():
    return redirect(GITHUB_PAGE_URL)

@app.route('/favicon.ico')
def favicon():
    return redirect("https://cdn.discordapp.com/app-icons/1477325845277184112/6a7d1d2360e2cfcb656f221e6b00f908.png")

def run_flask():
    import logging
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    app.run(host='0.0.0.0', port=8080)

Thread(target=run_flask, daemon=True).start()

# ==================== CONFIGS ====================
TOKEN = os.getenv('TOKEN')

SERVER_ID           = 405506950562840577
REGISTER_CHANNEL_ID = 1486425299502764105
BOT_SPAM_CHANNEL_ID = 869818537793966090

ROLE_KD2 = 1477322781774450868
ROLE_KD3 = 1477322769825005599
ROLE_KD4 = 1477322732201971945
ROLE_KD5 = 1477322675612553296
KD_ROLES = [ROLE_KD2, ROLE_KD3, ROLE_KD4, ROLE_KD5]

ROLE_SUSPEITO      = 1483271684722131025
ROLE_SUSPEITO_PLUS = 1483271744713130147
ROLE_CHEATER       = 1483272069042147389
SUSPEITA_ROLES     = [ROLE_SUSPEITO, ROLE_SUSPEITO_PLUS, ROLE_CHEATER]

ADM_CHAT_CHANNEL_ID     = 405658596051779584
ADM_COMMANDS_CHANNEL_ID = 405665188566532097  # Canal de comandos admin (testes)
LOGS_CHANNEL_ID     = 1487221094174818495
STAFF_ROLE_ID       = 472110979790929922
DEDO_USER_ID        = 84299190288523264
ROLE_FAZENDEIRO     = 1489771074945155113  # Ignora alerta de Human% baixo no log diário

# ================== SALAS TEMPORÁRIAS ==================

# Canais de criação → (categoria destino, nome da sala, emoji)
VOICE_TRIGGER_MAP = {
    1439347853834064090: (459529456663396372,  "🪖 Squad do {nick}"),   # Criar Squad Battlefield
    1487547455435178176: (459529456663396372,  "🪖 Squad do {nick}"),   # Criar Squad BF1
    1440679700925120543: (1440680027552350208, "🏟️ Squad do {nick}"),   # Criar Squad Arena
    1439345126584483851: (1432911097324765275, "⭕ Duo do {nick}"),     # Criar Duo RedSec
    1439344833624936771: (1432911097324765275, "⭕ Squad do {nick}"),   # Criar Squad RedSec
    1477351422868721674: (1432911097324765275, "⭕ Squad KD2+ do {nick}"), # Criar Squad KD2+
    1477363524354441267: (1432911097324765275, "⭕ Squad KD3+ do {nick}"), # Criar Squad KD3+
    1477365476387721403: (1432911097324765275, "⭕ Squad KD4+ do {nick}"), # Criar Squad KD4+
    1477365937043800255: (1432911097324765275, "⭕ Squad KD5+ do {nick}"), # Criar Squad KD5+
    1449414825779138761: (1449414337977520312, "🏆 Squad do {nick}"),   # Criar Sala Competitiva
}

# Canais fixos que NUNCA devem ser deletados pelo bot
VOICE_PROTECTED_CHANNELS = {
    1341566545230561322,  # Lobby Battlefield
    1440683314942967918,  # Lobby Arena/Gauntlet
    1432919538525016124,  # Lobby RedSec
    1449414468512649328,  # Lobby Competitivo
    1449434543839903837,  # chat-competitivo (texto)
}

# Rastreia salas criadas pelo bot: canal_id → criador_id
_temp_voice_channels: set[int] = set()
_voice_cooldowns: dict[int, float] = {}   # user_id → timestamp do último processamento
VOICE_COOLDOWN_SECONDS = 5

GIF_EA_ID    = "https://i.imgur.com/8hmECSV.gif"
GIF_DataShare = "https://i.imgur.com/2Qp2qAI.gif"

BASE_STATS_URL = (
    "https://api.gametools.network/bf6/stats/"
    "?categories=multiplayer&raw=false&format_values=true"
    "&seperation=false&skip_battlelog=true"
)

# ================== BANCO DE DADOS (JSON) ==================
DATA_DIR  = "/data" if os.path.exists("/data") else os.path.join(os.path.dirname(__file__), "data")
DATA_FILE = os.path.join(DATA_DIR, "users.json")

def load_users() -> dict:
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERRO] Falha ao carregar users.json: {e}")
        return {}

def save_users(users: dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

# ==================== BOT ====================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = discord.Bot(intents=intents)

# ================== HELPERS DE API ==================
def make_session() -> requests.Session:
    session = requests.Session()
    retries = Retry(total=1, backoff_factor=1, status_forcelist=[502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retries))
    return session

def make_links(gamertag: str, platform: str, persona_id: str = None, nucleus_id: str = None) -> str:
    """Gera links clicáveis [Stats] e [JSON] sem thumbnail para uso nos canais de log/ADM."""
    stats_link = f"[Stats](<https://gametools.network/stats/{platform}/name/{gamertag}?game=bf6>)"
    if persona_id and nucleus_id:
        json_url  = f"https://api.gametools.network/bf6/stats/?playerid={persona_id}&nucleus_id={nucleus_id}&platform={platform}"
    else:
        json_url  = f"https://api.gametools.network/bf6/stats/?name={gamertag}&platform={platform}"
    json_link = f"[JSON](<{json_url}>)"
    return f"{stats_link} | {json_link}"

def resolve_player_ids(gamertag: str) -> tuple:
    """Busca personaId e nucleusId via /bf6/player. Retorna (persona_id, nucleus_id) ou (None, None)."""
    session = make_session()
    try:
        resp = session.get(
            f"https://api.gametools.network/bf6/player?name={gamertag}",
            timeout=30
        )
        if resp.status_code != 200:
            return None, None
        personas = resp.json().get('results', [])
        if not personas:
            return None, None
        # Prioridade 1: cem_ea_id
        for p in personas:
            if p.get('platformId') == 'cem_ea_id':
                return p.get('personaId'), p.get('nucleusId')
        # Prioridade 2: steam ou origin
        for p in personas:
            if p.get('platformId') in ['steam', 'origin']:
                return p.get('personaId'), p.get('nucleusId')
        # Prioridade 3: qualquer persona
        return personas[0].get('personaId'), personas[0].get('nucleusId')
    except Exception:
        return None, None

def fetch_stats(gamertag: str, platform: str):
    """
    Busca stats com fallback automático:
    1. Tenta pelo nome + plataforma
    2. Se KD vier zerado ou Redsec não encontrado, busca personaId/nucleusId via /bf6/player
    3. Refaz a busca de stats com os IDs corretos (prioriza cem_ea_id, depois steam/origin)
    Retorna:
      - dict       → sucesso
      - None       → jogador não encontrado
      - "api_error" → instabilidade na API de stats (erro 500 ou falha de conexão)
    """
    session = make_session()
    api_failed = False  # Sinaliza se houve erro de infraestrutura da API

    # --- Tentativa 1: pelo nome + plataforma ---
    try:
        url = f"{BASE_STATS_URL}&name={gamertag}&platform={platform}"
        resp = session.get(url, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            kd, _ = _extract_redsec_kd(data)
            if kd > 0.0:
                return data  # Sucesso direto
            # KD zerado — tenta fallback
        elif resp.status_code == 500:
            api_failed = True
        # Outros status != 200 — tenta fallback
    except Exception:
        api_failed = True

    # --- Tentativa 2: busca personaId/nucleusId via /bf6/player ---
    try:
        player_resp = session.get(
            f"https://api.gametools.network/bf6/player?name={gamertag}",
            timeout=30
        )
        if player_resp.status_code != 200:
            # Se o player lookup também falhou por erro de servidor, sinaliza
            if player_resp.status_code == 500:
                api_failed = True
            return "api_error" if api_failed else None

        personas = player_resp.json().get('results', [])
        if not personas:
            return None

        persona_id = nucleus_id = None

        # Prioridade 1: cem_ea_id
        for p in personas:
            if p.get('platformId') == 'cem_ea_id':
                persona_id = p.get('personaId')
                nucleus_id = p.get('nucleusId')
                break

        # Prioridade 2: steam ou origin
        if not persona_id:
            for p in personas:
                if p.get('platformId') in ['steam', 'origin']:
                    persona_id = p.get('personaId')
                    nucleus_id = p.get('nucleusId')
                    break

        # Prioridade 3: qualquer persona disponível
        if not persona_id:
            persona_id = personas[0].get('personaId')
            nucleus_id = personas[0].get('nucleusId')

        if not persona_id or not nucleus_id:
            return None

        # --- Tentativa 3: stats pelo playerid + nucleus_id ---
        fixed_url = f"{BASE_STATS_URL}&playerid={persona_id}&nucleus_id={nucleus_id}&platform={platform}"
        resp2 = session.get(fixed_url, timeout=15)
        if resp2.status_code == 200:
            return resp2.json()
        elif resp2.status_code == 500:
            api_failed = True

    except Exception:
        api_failed = True

    return "api_error" if api_failed else None

def _extract_redsec_kd(data: dict) -> tuple:
    """Auxiliar: extrai apenas o KD do Redsec para decisão de fallback."""
    kd = 0.0
    for group in data.get('gameModeGroups', []):
        if group.get('gamemodeName') == 'Redsec':
            try:
                kd = float(group.get('killDeath', 0.0))
            except (ValueError, TypeError):
                kd = 0.0
            return kd, True
    for mode in data.get('gameModes', []):
        if mode.get('gamemodeName') in ['Redsec Squad', 'Redsec Duo', 'Redsec Solo']:
            try:
                kd = float(mode.get('killDeath', 0.0))
            except (ValueError, TypeError):
                kd = 0.0
            if kd > 0.0:
                return kd, True
    return 0.0, False

def extract_kd_and_human(data: dict) -> tuple:
    """Extrai KD do Redsec e human% do JSON de stats. Retorna (kd, human_pct)."""
    kd, _ = _extract_redsec_kd(data)

    try:
        raw = data.get('humanPrecentage', '0') or '0'
        human_pct = float(str(raw).replace('%', '').strip())
    except (ValueError, AttributeError):
        human_pct = 0.0

    return kd, human_pct

def extract_kd_by_mode(data: dict) -> dict:
    """Extrai KD individual de cada modo: Squad, Duo, Solo, Gauntlet."""
    modos = {
        'Redsec Squad': 'Squad',
        'Redsec Duo':   'Duo',
        'Redsec Solo':  'Solo',
        'Gauntlet':     'Gauntlet',
    }
    resultado = {v: 0.0 for v in modos.values()}
    for mode in data.get('gameModes', []):
        nome = mode.get('gamemodeName', '')
        if nome in modos:
            try:
                resultado[modos[nome]] = float(mode.get('killDeath', 0.0))
            except (ValueError, TypeError):
                resultado[modos[nome]] = 0.0
    return resultado

def build_stats_embed(data: dict, gamertag: str, platform: str, member=None, registered_at: str = None) -> discord.Embed:
    """Monta o embed padronizado de stats para /stats, /minha_conta e /search_player."""
    kd_val, human_pct = extract_kd_and_human(data)
    kd_modos          = extract_kd_by_mode(data)

    # Cor baseada no Human%
    if human_pct == 0.0:
        color = discord.Color.greyple()
    elif human_pct >= 70.0:
        color = discord.Color.green()
    elif human_pct >= 50.0:
        color = discord.Color.gold()
    else:
        color = discord.Color.red()

    # Accuracy e headshots do JSON
    try:
        accuracy  = data.get('accuracy', '0%')
        headshots = data.get('headshots', '0%')
    except Exception:
        accuracy  = '0%'
        headshots = '0%'

    # winPercent do modo Redsec
    win_pct = '0%'
    for mode in data.get('gameModes', []):
        if mode.get('gamemodeName') == 'Redsec Squad':
            win_pct = mode.get('winPercent', '0%')
            break

    # Título: menciona membro se cadastrado, senão só gamertag
    if member:
        title_str = f"Stats de {member.mention} (`{gamertag}` | `{platform}`)"
    else:
        title_str = f"Stats de `{gamertag}` | `{platform}`"

    embed = discord.Embed(description=title_str, color=color)

    # Avatar como thumbnail se membro conhecido
    if member and member.display_avatar:
        embed.set_thumbnail(url=member.display_avatar.url)

    # Campos principais
    embed.add_field(name="✅ KD Redsec atual", value=f"**{kd_val:.2f}**", inline=False)
    embed.add_field(name="🧠 Human%",          value=f"**{human_pct:.2f}%**", inline=True)
    embed.add_field(name="🎯 Accuracy",         value=f"**{accuracy}**",       inline=True)
    embed.add_field(name="💀 Headshots",        value=f"**{headshots}**",      inline=True)
    embed.add_field(name="🥇 1° lugar",         value=f"**{win_pct}**",        inline=True)

    # KD por modo inline
    embed.add_field(name="KD Squad",   value=f"{kd_modos['Squad']:.2f}",   inline=True)
    embed.add_field(name="KD Duo",     value=f"{kd_modos['Duo']:.2f}",     inline=True)
    embed.add_field(name="KD Solo",    value=f"{kd_modos['Solo']:.2f}",    inline=True)
    embed.add_field(name="KD Gauntlet",value=f"{kd_modos['Gauntlet']:.2f}",inline=True)

    # Rodapé com data de cadastro se disponível
    footer_parts = []
    if registered_at:
        try:
            dt = datetime.fromisoformat(registered_at)
            footer_parts.append(f"Cadastrado em {dt.strftime('%d/%m/%Y')}")
        except Exception:
            pass
    footer_parts.append(f"Consultado em {datetime.now(timezone(timedelta(hours=-3))).strftime('%d/%m/%Y %H:%M')} (BRT)")
    embed.set_footer(text=" • ".join(footer_parts))

    return embed, kd_val, human_pct

def classificar_suspeita(human_pct: float) -> tuple:
    """
    Retorna (role_id_ou_None, nome_interno, nome_publico).
    nome_interno: valor real — usado no canal ADM e no /hc.
    nome_publico: o que o jogador vê ao se registrar ou usar /kd.
    Jogadores suspeitos veem apenas 'Suspeito', sem saber o nível exato.
    """
    if human_pct == 0.0:
        return None, "Human% indisponível", "Human% indisponível"
    elif human_pct >= 70.0:
        return None, "Honesto", "Honesto"
    elif human_pct >= 50.0:
        return ROLE_SUSPEITO, "Sus 50-70%", "Suspeito"
    elif human_pct >= 30.0:
        return ROLE_SUSPEITO_PLUS, "Sus 30-50%", "Suspeito"
    else:
        return ROLE_CHEATER, "Cheater 0-30%", "Suspeito"

async def apply_roles(member: discord.Member, guild: discord.Guild, kd: float, human_pct: float) -> dict:
    """Aplica roles de KD e suspeita. Retorna dict com as mudanças."""
    changes = {}

    # --- Suspeita ---
    for role_id in SUSPEITA_ROLES:
        role = guild.get_role(role_id)
        if role and role in member.roles:
            await member.remove_roles(role)

    suspeita_role_id, suspeita_interno, suspeita_publico = classificar_suspeita(human_pct)

    if suspeita_role_id:
        suspeita_role = guild.get_role(suspeita_role_id)
        if suspeita_role:
            await member.add_roles(suspeita_role)

    changes['suspeita_interno'] = suspeita_interno
    changes['suspeita_publico'] = suspeita_publico
    changes['human_pct'] = human_pct

    # --- KD ---
    for role_id in KD_ROLES:
        role = guild.get_role(role_id)
        if role and role in member.roles:
            await member.remove_roles(role)

    kd_role_id = None
    if 2.0 <= kd < 3.0:
        kd_role_id, role_name = ROLE_KD2, 'Redsec KD2'
    elif 3.0 <= kd < 4.0:
        kd_role_id, role_name = ROLE_KD3, 'Redsec KD3'
    elif 4.0 <= kd < 5.0:
        kd_role_id, role_name = ROLE_KD4, 'Redsec KD4'
    elif kd >= 5.0:
        kd_role_id, role_name = ROLE_KD5, 'Redsec KD5+'
    else:
        role_name = 'Nenhuma (KD abaixo de 2.0)'

    if kd_role_id:
        new_role = guild.get_role(kd_role_id)
        if new_role:
            await member.add_roles(new_role)

    changes['kd'] = kd
    changes['kd_role'] = role_name
    return changes

# ================== MODAL DE REGISTRO ==================
class RegisterModal(Modal):
    def __init__(self):
        super().__init__(title="Registre sua conta EA")
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
        gamertag     = self.children[0].value.strip()
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

                # Avisa ADM com valor real
                if changes['suspeita_interno'] not in ["Honesto", "Human% indisponível"]:
                    adm_channel = bot.get_channel(ADM_CHAT_CHANNEL_ID)
                    if adm_channel:
                        await adm_channel.send(
                            f"⚠️ Suspeita detectada no **registro**:\n"
                            f"Usuário: {member.mention} (ID: {member.id})\n"
                            f"Gamertag: **{gamertag}** ({platform_raw})\n"
                            f"Human%: **{human_pct:.2f}%** → **{changes['suspeita_interno']}** | "
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
            stats_url = f"https://gametools.network/stats/{platform_raw}/name/{gamertag}?game=bf6"
            await logs_ch.send(
                f"📋 **Registro** | {interaction.user.mention} (`{interaction.user.id}`)\n"
                f"Gamertag: `{gamertag}` | Plataforma: `{platform_raw}` | Ação: **{action}**\n"
                f"KD: **{kd_val:.2f}** → **{changes['kd_role']}** | Human%: **{human_pct:.2f}%** | "
                f"{make_links(gamertag, platform_raw, persona_id, nucleus_id)}"
            )

# ================== BOTAO DE REGISTRO ==================
class RegisterView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="⭕ Registre-se aqui!", style=discord.ButtonStyle.primary, custom_id="register_button")
    async def register_button(self, button: Button, interaction: discord.Interaction):
        await interaction.response.send_modal(RegisterModal())

# ================== SALAS TEMPORÁRIAS (VOICE) ==================
@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    if member.guild.id != SERVER_ID:
        return

    # ── Entrou num canal de criação ──────────────────────────────────────────
    if after.channel and after.channel.id in VOICE_TRIGGER_MAP:
        # Cooldown aplicado APENAS na criação de sala (não afeta deleção)
        agora_ts = time.monotonic()
        ultimo   = _voice_cooldowns.get(member.id, 0)
        if agora_ts - ultimo < VOICE_COOLDOWN_SECONDS:
            return
        _voice_cooldowns[member.id] = agora_ts

        trigger     = after.channel
        category_id, name_template = VOICE_TRIGGER_MAP[trigger.id]
        category    = member.guild.get_channel(category_id)
        if not category:
            return

        nick      = member.display_name or member.name
        sala_nome = name_template.format(nick=nick)

        overwrites = dict(trigger.overwrites)
        overwrites[member] = discord.PermissionOverwrite(
            move_members=True,
            connect=True,
            speak=True,
        )

        try:
            new_channel = await member.guild.create_voice_channel(
                name=sala_nome,
                category=category,
                overwrites=overwrites,
                user_limit=trigger.user_limit or 0,
                bitrate=trigger.bitrate,
                rtc_region=trigger.rtc_region,
            )
            _temp_voice_channels.add(new_channel.id)
            await member.move_to(new_channel)
        except discord.Forbidden:
            print(f"[VOICE] Sem permissão para criar canal em '{category.name}'")
        except Exception as e:
            print(f"[VOICE] Erro ao criar sala: {e}")
        return

    # ── Saiu de um canal — verifica se deve deletar ─────────────────────────
    # Funciona mesmo após reinício do bot (quando _temp_voice_channels está vazio)
    if before.channel:
        channel     = before.channel
        in_memory   = channel.id in _temp_voice_channels
        in_category = (
            channel.category_id in VOICE_TARGET_CATEGORIES
            and channel.id not in VOICE_PROTECTED_CHANNELS
            and channel.id not in VOICE_TRIGGER_MAP
        )
        if (in_memory or in_category) and len(channel.members) == 0:
            try:
                await channel.delete(reason="Sala temporária vazia")
            except discord.Forbidden:
                print(f"[VOICE] Sem permissão para deletar '{channel.name}'")
            except Exception as e:
                print(f"[VOICE] Erro ao deletar sala: {e}")
            finally:
                _temp_voice_channels.discard(channel.id)

# ================== EVENTOS ==================
@bot.event
async def on_ready():
    print(f'{bot.user} online!')
    bot.add_view(RegisterView())
    try:
        await bot.sync_commands()
        print('Comandos slash sincronizados.')
    except Exception as e:
        print(f'Erro ao sincronizar comandos: {e}')

    bot.loop.create_task(auto_update_loop())
    bot.loop.create_task(voice_sweep_loop())

# ================== VARREDURA DE SALAS VAZIAS (04:00) ==================
# Categorias monitoradas pela varredura
VOICE_TARGET_CATEGORIES = {
    459529456663396372,   # 🪖 Jogando Battlefield
    1440680027552350208,  # 🏟️ Jogando Arena/Gauntlet
    1432911097324765275,  # ⭕ Jogando RedSec
    1449414337977520312,  # 🏆 Competitivo
}

# Nome legível de cada categoria monitorada (para o relatório)
VOICE_CATEGORY_NAMES = {
    459529456663396372:   "🪖 Jogando Battlefield",
    1440680027552350208:  "🏟️ Jogando Arena/Gauntlet",
    1432911097324765275:  "⭕ Jogando RedSec",
    1449414337977520312:  "🏆 Competitivo",
}

async def voice_sweep_loop():
    await bot.wait_until_ready()
    HORARIO_SWEEP = 4  # Mesmo horário do auto-update (04:00 Brasília)
    FUSO_BRASILIA = timezone(timedelta(hours=-3))

    while not bot.is_closed():
        try:
            agora   = datetime.now(FUSO_BRASILIA)
            proximo = agora.replace(hour=HORARIO_SWEEP, minute=0, second=30, microsecond=0)  # +30s após o auto-update
            if agora >= proximo:
                proximo += timedelta(days=1)
            espera  = (proximo - agora).total_seconds()
            print(f"[VOICE-SWEEP] Próxima varredura às {proximo.strftime('%d/%m/%Y %H:%M')} (Brasília). Aguardando {espera/3600:.1f}h.")
            await asyncio.sleep(espera)
            salas_deletadas = await run_voice_sweep()
            # Reporta no canal de logs se deletou salas
            if salas_deletadas > 0:
                logs_ch = bot.get_channel(LOGS_CHANNEL_ID)
                if logs_ch:
                    await logs_ch.send(f"🧹 Varredura 04:00 — **{salas_deletadas}** sala(s) de voz vazia(s) removida(s).")
        except Exception as e:
            print(f"[VOICE-SWEEP] Erro no loop: {e}")
            await asyncio.sleep(60)

async def run_voice_sweep() -> int:
    print(f"[VOICE-SWEEP] Iniciando varredura - {datetime.utcnow().isoformat()}")
    guild = bot.get_guild(SERVER_ID)
    if not guild:
        print("[VOICE-SWEEP] Servidor não encontrado.")
        return 0

    deletados = 0
    for channel in list(guild.voice_channels):
        # Só canais nas categorias monitoradas
        if not channel.category_id or channel.category_id not in VOICE_TARGET_CATEGORIES:
            continue
        # Nunca toca nos canais protegidos (lobbies, etc.)
        if channel.id in VOICE_PROTECTED_CHANNELS:
            continue
        # Nunca toca nos canais de criação (triggers)
        if channel.id in VOICE_TRIGGER_MAP:
            continue
        # Só deleta se estiver vazio
        if len(channel.members) == 0:
            try:
                await channel.delete(reason="Varredura 04:00 — sala vazia")
                deletados += 1
            except discord.Forbidden:
                print(f"[VOICE-SWEEP] Sem permissão para deletar '{channel.name}'")
            except Exception:
                pass
            finally:
                _temp_voice_channels.discard(channel.id)

    print(f"[VOICE-SWEEP] Concluída. Salas removidas: {deletados}")
    return deletados

# ================== ATUALIZACAO AUTOMATICA (24H) ==================
async def auto_update_loop():
    await bot.wait_until_ready()
    HORARIO_UPDATE = 4  # Hora de Brasília para rodar o update (04:00)
    FUSO_BRASILIA  = timezone(timedelta(hours=-3))

    while not bot.is_closed():
        try:
            agora    = datetime.now(FUSO_BRASILIA)
            # Calcula quantos segundos faltam para a próxima vez que chegar em HORARIO_UPDATE:00
            proximo  = agora.replace(hour=HORARIO_UPDATE, minute=0, second=0, microsecond=0)
            if agora >= proximo:
                proximo += timedelta(days=1)  # Já passou hoje, agenda para amanhã
            espera   = (proximo - agora).total_seconds()
            print(f"[AUTO-UPDATE] Próximo update às {proximo.strftime('%d/%m/%Y %H:%M')} (Brasília). Aguardando {espera/3600:.1f}h.")
            await asyncio.sleep(espera)
            await run_auto_update()
        except Exception as e:
            print(f"[AUTO-UPDATE] Erro no loop: {e}")
            await asyncio.sleep(60)  # Espera 1 minuto e tenta calcular de novo

async def run_auto_update():
    print(f"[AUTO-UPDATE] Iniciando - {datetime.utcnow().isoformat()}")
    guild = bot.get_guild(SERVER_ID)
    if not guild:
        print("[AUTO-UPDATE] Servidor não encontrado.")
        return

    adm_channel = bot.get_channel(ADM_CHAT_CHANNEL_ID)
    staff_role  = guild.get_role(STAFF_ROLE_ID)
    users       = load_users()

    if not users:
        print("[AUTO-UPDATE] Nenhum usuário registrado.")
        return

    total         = len(users)
    updated       = 0
    failed        = 0
    kd_changes    = []   # Mudanças reais de role de KD
    sus_alerts    = []   # Human% baixo detectado
    fail_details  = []   # Detalhes de falhas
    removed_users = {}   # Usuários que saíram do servidor

    for discord_id, info in list(users.items()):
        gamertag = info.get('gamertag')
        platform = info.get('platform', 'pc')

        try:
            member = guild.get_member(int(discord_id))
            if not member:
                print(f"[AUTO-UPDATE] Membro {discord_id} não está no servidor, removendo do JSON.")
                removed_users[discord_id] = info
                continue

            old_kd_roles      = [r for r in member.roles if r.id in KD_ROLES]
            old_suspeita_roles = [r for r in member.roles if r.id in SUSPEITA_ROLES]

            persona_id = info.get('persona_id')
            nucleus_id = info.get('nucleus_id')

            # Se tiver IDs salvos, usa direto sem passar pelo /bf6/player
            if persona_id and nucleus_id:
                fixed_url = f"{BASE_STATS_URL}&playerid={persona_id}&nucleus_id={nucleus_id}&platform={platform}"
                session   = make_session()
                try:
                    resp = session.get(fixed_url, timeout=15)
                    data = resp.json() if resp.status_code == 200 else None
                    if data is None:
                        data = "api_error" if resp.status_code == 500 else None
                except Exception:
                    data = "api_error"
            else:
                data = await asyncio.to_thread(fetch_stats, gamertag, platform)
                # Se conseguiu dados, resolve e salva os IDs para próximas vezes
                if data and data != "api_error":
                    pid, nid = await asyncio.to_thread(resolve_player_ids, gamertag)
                    if pid and nid:
                        users[discord_id]['persona_id'] = pid
                        users[discord_id]['nucleus_id']  = nid
                        save_users(users)

            if data == "api_error":
                print(f"[AUTO-UPDATE] API instável para {gamertag}, mantendo roles.")
                fail_details.append(f"- {member.mention} `{gamertag}` ({platform}) — API de stats instável")
                failed += 1
                continue
            if data is None:
                print(f"[AUTO-UPDATE] {gamertag} não encontrado na API, mantendo roles.")
                fail_details.append(f"- {member.mention} `{gamertag}` ({platform}) — ID não encontrado na API")
                failed += 1
                continue

            kd_val, human_pct = extract_kd_and_human(data)

            if kd_val == 0.0:
                print(f"[AUTO-UPDATE] {gamertag} sem stats no Redsec, mantendo roles.")
                fail_details.append(f"- {member.mention} `{gamertag}` ({platform}) — Sem partidas no Redsec")
                failed += 1
                continue

            changes = await apply_roles(member, guild, kd_val, human_pct)
            updated += 1

            new_kd_roles      = [r for r in member.roles if r.id in KD_ROLES]
            new_suspeita_roles = [r for r in member.roles if r.id in SUSPEITA_ROLES]
            kd_changed        = set(r.id for r in old_kd_roles) != set(r.id for r in new_kd_roles)
            suspeita_changed  = set(r.id for r in old_suspeita_roles) != set(r.id for r in new_suspeita_roles)
            is_sus            = changes['suspeita_interno'] not in ["Honesto", "Human% indisponível"]
            stats_url         = f"https://gametools.network/stats/{platform}/name/{gamertag}?game=bf6"

            if kd_changed:
                old_kd_name = old_kd_roles[0].name if old_kd_roles else "Nenhuma"
                kd_changes.append(
                    f"- {member.mention} (`{gamertag}` | {platform}) | "
                    f"KD: **{kd_val:.2f}** | **{old_kd_name}** → **{changes['kd_role']}** | "
                    f"<{stats_url}>"
                )
            if is_sus:
                fazendeiro_role = member.guild.get_role(ROLE_FAZENDEIRO)
                is_fazendeiro   = fazendeiro_role and fazendeiro_role in member.roles
                if not is_fazendeiro:
                    sus_alerts.append(
                        f"- {member.mention} (`{gamertag}` | {platform}) | "
                        f"KD: **{kd_val:.2f}** | Human%: **{human_pct:.2f}%** → **{changes['suspeita_interno']}** | "
                        f"{make_links(gamertag, platform, persona_id, nucleus_id)}"
                    )

            await asyncio.sleep(5)

        except Exception as e:
            print(f"[AUTO-UPDATE] Erro ao processar {discord_id}: {e}")
            failed += 1
            continue

    # Remove do JSON quem saiu do servidor
    if removed_users:
        for discord_id in removed_users:
            users.pop(discord_id, None)
        save_users(users)
        print(f"[AUTO-UPDATE] {len(removed_users)} usuário(s) removido(s) do JSON.")

    logs_channel = bot.get_channel(LOGS_CHANNEL_ID)
    if logs_channel:
        dedo_mention = f"<@{DEDO_USER_ID}> " if failed > 0 else ""
        summary = (
            f"{dedo_mention}**Atualização automática concluída!**\n"
            f"Total registrados: **{total}** | Atualizados: **{updated}** | Falhas (roles mantidas): **{failed}**\n"
        )
        await logs_channel.send(summary)

        if sus_alerts:
            msg = f"**⚠️ Human% baixo detectado ({len(sus_alerts)}):**\n" + "\n".join(sus_alerts[:20])
            if len(sus_alerts) > 20:
                msg += f"\n*...e mais {len(sus_alerts) - 20}.*"
            await logs_channel.send(msg)

        if fail_details:
            msg = f"**❌ Detalhes das falhas ({len(fail_details)}):**\n" + "\n".join(fail_details[:20])
            if len(fail_details) > 20:
                msg += f"\n*...e mais {len(fail_details) - 20}.*"
            await logs_channel.send(msg)

        if removed_users:
            removed_lines = []
            for discord_id, info in removed_users.items():
                gt     = info.get('gamertag', '?')
                plat   = info.get('platform', '?')
                reg_at = info.get('registered_at', '?')[:10]
                removed_lines.append(f"<@{discord_id}> | {gt} | {plat} | {reg_at}")
            msg = (
                f"🧹 **{len(removed_users)} usuário(s) removido(s) do registro** (saíram do servidor):\n"
                + "\n".join(removed_lines[:30])
            )
            if len(removed_users) > 30:
                msg += f"\n*...e mais {len(removed_users) - 30} removidos.*"
            await logs_channel.send(msg)

    print(f"[AUTO-UPDATE] Concluído. Atualizados: {updated} | Falhas: {failed}")

# ==================== COMANDOS ====================

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

    await channel.send(embed=embed, view=RegisterView())
    await ctx.respond(f"✅ Painel de registro enviado em {channel.mention}!", ephemeral=True)

@bot.slash_command(name="force_update", description="[ADMIN] Força a atualização de todos os registrados agora")
@discord.default_permissions(administrator=True)
async def force_update(ctx: discord.ApplicationContext):
    logs_channel = bot.get_channel(LOGS_CHANNEL_ID)
    logs_mention = logs_channel.mention if logs_channel else f"<#{LOGS_CHANNEL_ID}>"
    await ctx.respond(f"🔄 Atualização forçada iniciada! Acompanhe o resultado em {logs_mention}.", ephemeral=True)
    await run_auto_update()

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

    # Mapa de lobby por categoria (para somar pessoas do lobby na contagem)
    LOBBY_POR_CATEGORIA = {
        459529456663396372:   1341566545230561322,  # Battlefield
        1440680027552350208:  1440683314942967918,  # Arena/Gauntlet
        1432911097324765275:  1432919538525016124,  # RedSec
        1449414337977520312:  1449414468512649328,  # Competitivo
    }

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
    pid, nid = await asyncio.to_thread(resolve_player_ids, gamertag)
    entry_fr = {
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
        adm_channel = bot.get_channel(ADM_CHAT_CHANNEL_ID)
        if adm_channel:
            await adm_channel.send(
                f"⚠️ Suspeita detectada via **/force_register**:\n"
                f"Usuário: {member.mention} (ID: {member.id})\n"
                f"Gamertag: **{gamertag}** ({plataforma})\n"
                f"Human%: **{human_pct:.2f}%** → **{changes['suspeita_interno']}** | "
                f"{make_links(gamertag, plataforma, pid, nid)}\n"
                f"Registrado por: {ctx.author.mention}"
            )

    action    = "atualizado" if old_entry else "registrado"
    stats_url = f"https://gametools.network/stats/{plataforma}/name/{gamertag}?game=bf6"

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

    users = load_users()
    removed_id  = None
    removed_info = None

    if discord_id:
        if discord_id in users:
            removed_id   = discord_id
            removed_info = users[discord_id]
        else:
            await ctx.respond(f"❌ Discord ID `{discord_id}` não encontrado no registro.", ephemeral=True)
            return
    else:
        # Busca por gamertag (case-insensitive)
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

@bot.slash_command(name="ajuda", description="Mostra como usar o bot")
async def ajuda(ctx: discord.ApplicationContext):
    spam_channel = bot.get_channel(BOT_SPAM_CHANNEL_ID)
    spam_mention = spam_channel.mention if spam_channel else f"<#{BOT_SPAM_CHANNEL_ID}>"

    register_channel = bot.get_channel(REGISTER_CHANNEL_ID)
    register_mention = register_channel.mention if register_channel else f"<#{REGISTER_CHANNEL_ID}>"

    embed = discord.Embed(
        title="Como usar o bot de KD Redsec",
        description=(
            f"**Passo 1:** Vá até o canal `#registrar-kd-redsec⭕` ({register_mention}) e clique no botão **⭕ Registre-se aqui!**\n"
            "Após registrar, o bot atualiza suas roles automaticamente a cada **24 horas**.\n\n"
            f"**Comandos manuais** (use em {spam_mention}):\n"
            f"→ `/kd [SeuID] [plataforma]` — busca seu KD e atribui a role\n"
            f"→ `/stats [IDdaEA] [plataforma]` — stats completos (KD, Human%, Accuracy...)\n"f"→ `/minha_conta` — veja seus próprios stats e dados de cadastro\n\n"
            "**Plataformas válidas:** `pc` · `psn` · `xbox`\n\n"
            "**Como pegar seu ID da EA?** Veja o GIF abaixo!\n\n"
            "Qualquer dúvida, chama a staff!"
        ),
        color=discord.Color.blue()
    )
    embed.set_image(url=GIF_EA_ID)
    await ctx.respond(embed=embed)

@bot.slash_command(name="kd", description="Busca seu KD no Redsec e atribui role")
@discord.option("gamertag", description="Seu ID da EA", required=True)
@discord.option("plataforma", description="Plataforma", required=True, choices=["pc", "psn", "xbox"])
async def kd(ctx: discord.ApplicationContext, gamertag: str, plataforma: str):
    spam_channel = bot.get_channel(BOT_SPAM_CHANNEL_ID)
    spam_mention = spam_channel.mention if spam_channel else f"<#{BOT_SPAM_CHANNEL_ID}>"

    if ctx.channel_id not in (BOT_SPAM_CHANNEL_ID, ADM_COMMANDS_CHANNEL_ID):
        await ctx.respond(
            f"⚠️ Por favor, use os comandos de bot em {spam_mention}.",
            ephemeral=True
        )
        return

    await ctx.defer()
    await ctx.respond(
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

    guild = bot.get_guild(SERVER_ID)
    if not guild:
        await ctx.followup.send("❌ Erro interno: servidor não encontrado. Contate a staff!")
        return

    changes = await apply_roles(ctx.author, guild, kd_val, human_pct)

    # Salva no JSON (igual ao botão de registro)
    users_data  = load_users()
    disc_id_str = str(ctx.author.id)
    old_entry   = users_data.get(disc_id_str)
    pid, nid    = await asyncio.to_thread(resolve_player_ids, gamertag)
    entry_kd    = {
        "gamertag":      gamertag,
        "platform":      plataforma,
        "registered_at": datetime.utcnow().isoformat()
    }
    if pid and nid:
        entry_kd["persona_id"] = pid
        entry_kd["nucleus_id"] = nid
    users_data[disc_id_str] = entry_kd
    save_users(users_data)

    # Avisa ADM com valor real (após resolver pid/nid)
    if changes['suspeita_interno'] not in ["Honesto", "Human% indisponível"]:
        adm_channel = bot.get_channel(ADM_CHAT_CHANNEL_ID)
        if adm_channel:
            await adm_channel.send(
                f"⚠️ Suspeita detectada via **/kd**:\n"
                f"Usuário: {ctx.author.mention} (ID: {ctx.author.id})\n"
                f"Gamertag: **{gamertag}** ({plataforma})\n"
                f"Human%: **{human_pct:.2f}%** → **{changes['suspeita_interno']}** | "
                f"{make_links(gamertag, plataforma, pid, nid)}"
            )

    # Log no canal de logs
    logs_ch = bot.get_channel(LOGS_CHANNEL_ID)
    if logs_ch:
        stats_url_log = f"https://api.gametools.network/bf6/stats/?name={gamertag}&platform={plataforma}"
        if pid and nid:
            stats_url_log = f"https://api.gametools.network/bf6/stats/?playerid={pid}&nucleus_id={nid}&platform={plataforma}"
        action_log = "atualizado" if old_entry else "registrado"
        await logs_ch.send(
            f"📋 **Registro via /kd** | {ctx.author.mention} (`{ctx.author.id}`) | Ação: **{action_log}**\n"
            f"Gamertag: `{gamertag}` | Plataforma: `{plataforma}`\n"
            f"KD: **{kd_val:.2f}** → **{changes['kd_role']}** | Human%: **{human_pct:.2f}%** | "
            f"{make_links(gamertag, plataforma, pid, nid)}"
        )

    kd_modos = extract_kd_by_mode(data)
    if old_entry:
        nota = "ℹ️ Seus dados já estavam cadastrados e foram atualizados. O bot atualiza sua role automaticamente todo dia às 04:00!"
    else:
        nota = "✅ Seus dados foram salvos! O bot atualizará sua role automaticamente todo dia às 04:00."
    await ctx.followup.send(
        f"✅ KD **Redsec** atual: **{kd_val:.2f}**\n"
        f"Role atribuída: **{changes['kd_role']}**\n"
        f"KD Squad: **{kd_modos['Squad']:.2f}** | KD Duo: **{kd_modos['Duo']:.2f}** | "
        f"KD Solo: **{kd_modos['Solo']:.2f}** | KD Gauntlet: **{kd_modos['Gauntlet']:.2f}**\n"
        f"Status: **{changes['suspeita_publico']}**\n\n"
        f"{nota}"
    )

@bot.slash_command(name="stats", description="Mostra stats completos de um jogador no Redsec")
@discord.option("gamertag", description="ID da EA", required=True)
@discord.option("plataforma", description="Plataforma", required=True, choices=["pc", "psn", "xbox"])
async def stats(ctx: discord.ApplicationContext, gamertag: str, plataforma: str):
    spam_channel = bot.get_channel(BOT_SPAM_CHANNEL_ID)
    spam_mention = spam_channel.mention if spam_channel else f"<#{BOT_SPAM_CHANNEL_ID}>"

    if ctx.channel_id not in (BOT_SPAM_CHANNEL_ID, ADM_COMMANDS_CHANNEL_ID):
        await ctx.respond(f"⚠️ Por favor, use os comandos de bot em {spam_mention}.", ephemeral=True)
        return

    await ctx.defer()
    await ctx.respond(
        f"<a:buscabf6:1488347979524997171> Buscando stats de **{gamertag}** ({plataforma})...\n"
        f"*Pode demorar até 1 minuto.*"
    )

    data = await asyncio.to_thread(fetch_stats, gamertag, plataforma)

    if data == "api_error":
        await ctx.followup.send("⚠️ A API de stats está instável no momento. Tente novamente em alguns minutos.")
        return
    if data is None:
        await ctx.followup.send(
            f"❌ ID **{gamertag}** não encontrado na plataforma **{plataforma}**.\n"
            f"Verifique seu **ID da EA**. Como encontrar: {GIF_EA_ID}"
        )
        return

    # Verifica se o jogador está cadastrado no servidor
    guild  = bot.get_guild(SERVER_ID)
    member = None
    registered_at = None
    if guild:
        users = load_users()
        for uid, info in users.items():
            if info.get('gamertag', '').lower() == gamertag.lower() and info.get('platform') == plataforma:
                member        = guild.get_member(int(uid))
                registered_at = info.get('registered_at')
                break

    embed, kd_val, human_pct = build_stats_embed(data, gamertag, plataforma, member, registered_at)
    stats_url = f"<https://gametools.network/stats/{plataforma}/name/{gamertag}?game=bf6>"
    embed.add_field(name="🔗 Perfil", value=stats_url, inline=False)
    await ctx.followup.send(embed=embed)

@bot.slash_command(name="search_player", description="[ADMIN] Busca um jogador cadastrado por Discord ID ou gamertag")
@discord.default_permissions(administrator=True)
@discord.option("discord_id", description="Discord ID do usuário", required=False)
@discord.option("gamertag",   description="Gamertag (ID da EA) cadastrada no banco", required=False)
async def search_player(ctx: discord.ApplicationContext, discord_id: str = None, gamertag: str = None):
    if not discord_id and not gamertag:
        await ctx.respond("❌ Informe ao menos um: **discord_id** ou **gamertag**.", ephemeral=True)
        return

    users = load_users()
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

    data = await asyncio.to_thread(fetch_stats, gt, plat)
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

@bot.slash_command(name="minha_conta", description="Mostra seus stats e dados de cadastro")
async def minha_conta(ctx: discord.ApplicationContext):
    spam_channel = bot.get_channel(BOT_SPAM_CHANNEL_ID)
    spam_mention = spam_channel.mention if spam_channel else f"<#{BOT_SPAM_CHANNEL_ID}>"

    if ctx.channel_id not in (BOT_SPAM_CHANNEL_ID, ADM_COMMANDS_CHANNEL_ID):
        await ctx.respond(f"⚠️ Por favor, use este comando em {spam_mention}.", ephemeral=True)
        return

    users     = load_users()
    discord_id = str(ctx.author.id)
    if discord_id not in users:
        register_channel = bot.get_channel(REGISTER_CHANNEL_ID)
        register_mention = register_channel.mention if register_channel else "canal de registro"
        await ctx.respond(
            f"❌ Você ainda não está cadastrado!\n"
            f"Vá até {register_mention} e clique em **⭕ Registre-se aqui!**",
            ephemeral=True
        )
        return

    info          = users[discord_id]
    gt            = info.get('gamertag', '?')
    plat          = info.get('platform', 'pc')
    registered_at = info.get('registered_at', '')

    await ctx.defer(ephemeral=True)
    await ctx.respond(
        f"<a:buscabf6:1488347979524997171> Buscando seus stats (**{gt}** | {plat})...",
        ephemeral=True
    )

    data = await asyncio.to_thread(fetch_stats, gt, plat)

    if data == "api_error":
        await ctx.followup.send("⚠️ A API de stats está instável. Tente novamente em alguns minutos.", ephemeral=True)
        return
    if data is None:
        await ctx.followup.send(f"❌ Não foi possível encontrar seus stats. Verifique seu cadastro.", ephemeral=True)
        return

    embed, _, _ = build_stats_embed(data, gt, plat, ctx.author, registered_at)
    stats_url   = f"<https://gametools.network/stats/{plat}/name/{gt}?game=bf6>"
    embed.add_field(name="🔗 Perfil", value=stats_url, inline=False)
    await ctx.followup.send(embed=embed, ephemeral=True)

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
            users    = load_users()
            gt       = '?'
            plat     = '?'
            reg_at   = '?'
            info     = {}
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

@bot.event
async def on_application_command_error(ctx: discord.ApplicationContext, error: discord.DiscordException):
    """Handler de erros para slash commands."""
    if isinstance(error, discord.errors.CheckFailure):
        await ctx.respond("❌ Você não tem permissão para usar este comando.", ephemeral=True)
    else:
        print(f"[ERRO SLASH] {ctx.command}: {error}")
        try:
            await ctx.respond("❌ Ocorreu um erro inesperado. Tente novamente.", ephemeral=True)
        except Exception:
            pass

bot.run(TOKEN)
