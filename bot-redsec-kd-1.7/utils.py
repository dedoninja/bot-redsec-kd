import discord
from datetime import datetime, timezone, timedelta
from api import _extract_redsec_kd
from config import (
    KD_ROLES,
    ROLE_KD2, ROLE_KD3, ROLE_KD4, ROLE_KD5,
    RANK_ROLES,
    ROLE_RANK_ELITE, ROLE_RANK_MESTRE, ROLE_RANK_DIAMANTE, ROLE_RANK_PLATINA,
    ROLE_RANK_OURO, ROLE_RANK_PRATA, ROLE_RANK_BRONZE, ROLE_RANK_RECRUTA, ROLE_SEM_RANK,
)


def _extract_latest_season(data: dict) -> tuple:
    """Retorna (season_name, modes_dict) da última season em data['redsec'].

    season_name: string legível, ex: 'Season 3'
    modes_dict:  {'Squad': float, 'Duo': float, 'Solo': float, 'Gauntlet': float}

    Retorna (None, defaults) se não houver dados de redsec.
    """
    defaults = {'Squad': 0.0, 'Duo': 0.0, 'Solo': 0.0, 'Gauntlet': 0.0}
    redsec_seasons = data.get('redsec', [])
    if not redsec_seasons:
        return None, defaults

    # Maior seasonId lexicográfico (Season1 < Season2 < Season3...)
    latest = max(redsec_seasons, key=lambda s: s.get('seasonId', ''))
    season_name = latest.get('season', latest.get('seasonId', 'Season ?'))

    # Mapeia o campo 'mode' do JSON para chaves internas
    mode_map = {
        'Quads':    'Squad',
        'Duos':     'Duo',
        'Solo':     'Solo',
        'Gauntlet': 'Gauntlet',
    }
    resultado = dict(defaults)
    for mode in latest.get('modes', []):
        key = mode_map.get(mode.get('mode', ''))
        if key:
            try:
                resultado[key] = float(mode.get('killDeath', 0.0))
            except (ValueError, TypeError):
                resultado[key] = 0.0

    return season_name, resultado


def extract_kd_and_human(data: dict) -> tuple:
    """Extrai KD do Redsec (Squad da última season) e human% do JSON de stats.
    Retorna (kd, human_pct).
    """
    kd, _ = _extract_redsec_kd(data)

    try:
        raw = data.get('humanPrecentage', '0') or '0'
        human_pct = float(str(raw).replace('%', '').strip())
    except (ValueError, AttributeError):
        human_pct = 0.0

    return kd, human_pct


def extract_kd_by_mode(data: dict) -> dict:
    """Extrai KD individual de cada modo (Squad, Duo, Solo, Gauntlet) da última season."""
    _, modos = _extract_latest_season(data)
    return modos


def extract_br_kd(data: dict) -> float:
    """Extrai o killDeath do grupo 'Battle Royale' em gameModeGroups.
    É o mesmo valor usado para atribuir roles de KD.
    """
    for group in data.get('gameModeGroups', []):
        if group.get('gamemodeName') == 'Battle Royale':
            try:
                return float(group.get('killDeath', 0.0))
            except (ValueError, TypeError):
                return 0.0
    return 0.0


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


def get_rank_role_id(rank: int) -> tuple:
    """Retorna (role_id, role_name) de rank competitivo com base no valor numérico do rank.

    rank >= 36 → Rank Elite
    rank 31-35 → Rank Mestre
    rank 26-30 → Rank Diamante
    rank 21-25 → Rank Platina
    rank 16-20 → Rank Ouro
    rank 11-15 → Rank Prata
    rank 6-10  → Rank Bronze
    rank 1-5   → Rank Recruta
    rank == 0  → ROLE_SEM_RANK (cobre tanto 'Perfil Privado' quanto 'Unranked')
                 O nome exibido é determinado pelo rank_name retornado pela API em fetch_competitive_rank.
    """
    if rank >= 36:
        return ROLE_RANK_ELITE, 'Rank Elite'
    elif rank >= 31:
        return ROLE_RANK_MESTRE, 'Rank Mestre'
    elif rank >= 26:
        return ROLE_RANK_DIAMANTE, 'Rank Diamante'
    elif rank >= 21:
        return ROLE_RANK_PLATINA, 'Rank Platina'
    elif rank >= 16:
        return ROLE_RANK_OURO, 'Rank Ouro'
    elif rank >= 11:
        return ROLE_RANK_PRATA, 'Rank Prata'
    elif rank >= 6:
        return ROLE_RANK_BRONZE, 'Rank Bronze'
    elif rank >= 1:
        return ROLE_RANK_RECRUTA, 'Rank Recruta'
    else:
        return ROLE_SEM_RANK, 'Perfil Privado'


def build_stats_embed(
    data: dict,
    gamertag: str,
    platform: str,
    member=None,
    registered_at: str = None,
    discord_id: str = None,
    persona_id: str = None,
    nucleus_id: str = None,
    comp_rank: int = 0,
    comp_rank_name: str = None,
):
    """Monta o embed padronizado de stats para /stats, /minha_conta e /search_player.

    Parâmetros opcionais discord_id, persona_id, nucleus_id:
      - Quando fornecidos, inclui a seção 'Dados no bot' no embed
        (Discord ID, Persona ID, Nucleus ID, Cadastrado, Perfil, API JSON).
      - Quando ausentes (ex: /stats público), inclui apenas o link de Perfil.
    """
    kd_val, human_pct = extract_kd_and_human(data)
    season_name, kd_modos = _extract_latest_season(data)
    br_kd = extract_br_kd(data)

    # Cor baseada no Human%
    if human_pct == 0.0:
        color = discord.Color.greyple()
    elif human_pct >= 70.0:
        color = discord.Color.green()
    elif human_pct >= 50.0:
        color = discord.Color.gold()
    else:
        color = discord.Color.red()

    # Campos de Stats Gerais
    try:
        accuracy  = data.get('accuracy', '0%')
        headshots = data.get('headshots', '0%')
    except Exception:
        accuracy  = '0%'
        headshots = '0%'

    # 1° lugar, Kills, Partidas, KPM, DPM e Tempo vêm do grupo 'Battle Royale' em gameModeGroups
    win_pct  = '0%'
    br_kills   = 0
    br_matches = 0
    br_horas   = 0
    for group in data.get('gameModeGroups', []):
        if group.get('gamemodeName') == 'Battle Royale':
            win_pct    = group.get('winPercent', '0%')
            br_kills   = group.get('kills', 0)
            br_matches = group.get('matches', 0)
            try:
                br_horas = round(int(group.get('secondsPlayed', 0) or 0) / 3600)
            except (ValueError, TypeError):
                br_horas = 0
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

    # ── Stats Gerais Battle Royale ──
    embed.add_field(name="\u200b", value="📊 Stats Gerais Battle Royale", inline=False)
    embed.add_field(name="🧠 Human%",       value=f"**{human_pct:.2f}%**", inline=True)
    embed.add_field(name="🎯 Accuracy",     value=f"**{accuracy}**",       inline=True)
    embed.add_field(name="💀 Headshots",    value=f"**{headshots}**",      inline=True)
    embed.add_field(name="🥇 1° lugar",     value=f"**{win_pct}**",        inline=True)
    embed.add_field(name="☠️ Kills",        value=f"**{br_kills}**",       inline=True)
    embed.add_field(name="⚔️ Partidas",     value=f"**{br_matches}**",     inline=True)
    embed.add_field(name="✅ KD Battle Royale",  value=f"**{br_kd:.2f}**",                    inline=True)
    embed.add_field(name="🪖 KD Infantaria", value=f"**{extract_infantry_kd(data):.2f}**", inline=True)
    embed.add_field(name="⏱️ Tempo jogado",  value=f"**{br_horas}h**",                     inline=True)

    # ── Stats Season atual ──
    season_label = f"📈 Stats {season_name}" if season_name else "📈 Stats Season"
    embed.add_field(name="\u200b", value=season_label, inline=False)
    embed.add_field(name="KD Squad",    value=f"{kd_modos['Squad']:.2f}",    inline=True)
    embed.add_field(name="KD Duo",      value=f"{kd_modos['Duo']:.2f}",      inline=True)
    embed.add_field(name="KD Solo",     value=f"{kd_modos['Solo']:.2f}",     inline=True)
    embed.add_field(name="KD Gauntlet", value=f"{kd_modos['Gauntlet']:.2f}", inline=True)

    # Campo de Rank competitivo (ao lado de KD Gauntlet)
    rank_display = comp_rank_name if comp_rank_name else 'Perfil Privado'
    embed.add_field(name="🏆 Rank", value=rank_display, inline=True)

    # KD Gauntlet + Rank = 2 campos → 1 filler para fechar a linha de 3
    embed.add_field(name="\u200b", value="\u200b", inline=True)

    # ── Dados no bot (apenas quando discord_id/persona_id/nucleus_id fornecidos — comandos admin) ──
    if discord_id or persona_id or nucleus_id:
        if discord_id:
            embed.add_field(name="🆔 Discord ID", value=f"`{discord_id}`", inline=True)
        if persona_id:
            embed.add_field(name="🎮 Persona ID", value=f"`{persona_id}`", inline=True)
        if nucleus_id:
            embed.add_field(name="⚛️ Nucleus ID", value=f"`{nucleus_id}`", inline=True)

        # Data de cadastro
        if registered_at:
            try:
                reg_fmt = datetime.fromisoformat(registered_at).strftime('%d/%m/%Y')
            except Exception:
                reg_fmt = registered_at[:10]
            embed.add_field(name="📅 Cadastrado", value=reg_fmt, inline=True)

        # Link de perfil no /search_player aponta para battlefield.joarchy.com usando nucleus_id
        if nucleus_id:
            perfil_url = f"<https://battlefield.joarchy.com/p/{nucleus_id}>"
        else:
            perfil_url = f"<https://gametools.network/stats/{platform}/name/{gamertag}?game=bf6>"
        embed.add_field(name="🔗 Perfil", value=perfil_url, inline=False)

        if persona_id and nucleus_id:
            api_url = f"<https://api.gametools.network/bf6/stats/?playerid={persona_id}&nucleus_id={nucleus_id}>"
        else:
            api_url = f"<https://api.gametools.network/bf6/stats/?name={gamertag}>"
        embed.add_field(name="📡 API JSON", value=api_url, inline=False)

    # Rodapé
    footer_parts = []
    if registered_at and not (discord_id or persona_id or nucleus_id):
        try:
            dt = datetime.fromisoformat(registered_at)
            footer_parts.append(f"Cadastrado em {dt.strftime('%d/%m/%Y')}")
        except Exception:
            pass
    footer_parts.append(f"Consultado em {datetime.now(timezone(timedelta(hours=-3))).strftime('%d/%m/%Y %H:%M')} (BRT)")
    embed.set_footer(text=" • ".join(footer_parts))

    return embed, kd_val, human_pct


async def apply_roles(member: discord.Member, guild: discord.Guild, kd: float, human_pct: float, comp_rank: int = 0, rank_name: str = None) -> dict:
    changes = {}

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

    # --- Rank competitivo ---
    for role_id in RANK_ROLES:
        role = guild.get_role(role_id)
        if role and role in member.roles:
            await member.remove_roles(role)

    rank_role_id, rank_role_name_default = get_rank_role_id(comp_rank)
    rank_role = guild.get_role(rank_role_id)
    if rank_role:
        await member.add_roles(rank_role)

    # Usa o rank_name da API quando disponível (distingue 'Perfil Privado' de 'Unranked')
    # Para ranks com valor > 0, usa o nome padrão do get_rank_role_id
    changes['comp_rank'] = comp_rank
    changes['rank_role'] = rank_name if (rank_name and comp_rank == 0) else rank_role_name_default
    return changes
