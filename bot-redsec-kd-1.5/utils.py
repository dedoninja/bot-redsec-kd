import discord
from datetime import datetime, timezone, timedelta
from api import _extract_redsec_kd
from config import (
    KD_ROLES, SUSPEITA_ROLES,
    ROLE_SUSPEITO, ROLE_SUSPEITO_PLUS, ROLE_CHEATER,
    ROLE_KD2, ROLE_KD3, ROLE_KD4, ROLE_KD5,
)


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


def extract_infantry_kd(data: dict) -> float:
    """Extrai o KD de infantaria (infantryKillDeath) para o Top 5 Battlefield.
    Prioriza o campo direto no raiz do JSON, com fallback mínimo."""
    try:
        # Prioridade 1: Campo direto no raiz do JSON (mais comum)
        if 'infantryKillDeath' in data:
            return float(data.get('infantryKillDeath', 0) or 0)

        # Fallback 2: Procura dentro de gameModes (caso esteja aninhado)
        for mode in data.get('gameModes', []):
            if mode.get('infantryKillDeath') is not None:
                return float(mode.get('infantryKillDeath', 0) or 0)

        # Fallback 3: Procura em gameModeGroups
        for group in data.get('gameModeGroups', []):
            if group.get('infantryKillDeath') is not None:
                return float(group.get('infantryKillDeath', 0) or 0)

    except (ValueError, TypeError, AttributeError, KeyError):
        pass

    return 0.0


def build_stats_embed(data: dict, gamertag: str, platform: str, member=None, registered_at: str = None):
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

    # Accuracy, headshots e KD de infantaria do JSON
    try:
        accuracy     = data.get('accuracy', '0%')
        headshots    = data.get('headshots', '0%')
        infantry_kd  = float(data.get('infantryKillDeath', 0.0) or 0.0)
    except Exception:
        accuracy     = '0%'
        headshots    = '0%'
        infantry_kd  = 0.0

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
    embed.add_field(name="KD Squad",      value=f"{kd_modos['Squad']:.2f}",   inline=True)
    embed.add_field(name="KD Duo",        value=f"{kd_modos['Duo']:.2f}",     inline=True)
    embed.add_field(name="KD Solo",       value=f"{kd_modos['Solo']:.2f}",    inline=True)
    embed.add_field(name="KD Gauntlet",   value=f"{kd_modos['Gauntlet']:.2f}",inline=True)
    embed.add_field(name="KD Infantaria", value=f"{infantry_kd:.2f}",         inline=True)

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