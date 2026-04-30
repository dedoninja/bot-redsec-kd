import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from config import BASE_STATS_URL


def make_session() -> requests.Session:
    session = requests.Session()
    retries = Retry(total=1, backoff_factor=1, status_forcelist=[502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retries))
    return session


def make_links(gamertag: str, platform: str, persona_id: str = None, nucleus_id: str = None) -> str:
    """Gera links clicáveis [Stats] e [JSON] sem thumbnail para uso nos canais de log/ADM."""
    stats_link = f"[Stats](<https://gametools.network/stats/{platform}/name/{gamertag}?game=bf6>)"
    if persona_id and nucleus_id:
        json_url = f"https://api.gametools.network/bf6/stats/?playerid={persona_id}&nucleus_id={nucleus_id}"
    else:
        json_url = f"https://api.gametools.network/bf6/stats/?name={gamertag}"
    json_link = f"[JSON](<{json_url}>)"
    return f"{stats_link} | {json_link}"


def resolve_player_ids(gamertag: str) -> tuple:
    """
    Busca personaId e nucleusId via /bf6/player. Retorna (persona_id, nucleus_id) ou (None, None).
    
    NOVA LÓGICA COM FALLBACK:
    1. Prioriza cem_ea_id
    2. Se cem_ea_id tiver KD 0.00, busca steam/origin
    3. Se steam/origin também zerado, busca xbox/psn
    4. Se todos zerados, retorna o primeiro cem_ea_id mesmo assim
    """
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
        
        # Separa personas por tipo
        cem_ea = None
        steam_origin = None
        console = None
        
        for p in personas:
            pid = p.get('platformId')
            if pid == 'cem_ea_id':
                cem_ea = p
            elif pid in ['steam', 'origin']:
                steam_origin = p
            elif pid in ['xbox', 'xboxone', 'ps4', 'ps5']:
                console = p
        
        # Tenta cada tipo em ordem, verificando se tem stats
        for candidate in [cem_ea, steam_origin, console]:
            if candidate:
                pid = candidate.get('personaId')
                nid = candidate.get('nucleusId')
                if pid and nid:
                    # Verifica se essa conta tem stats no Redsec
                    if _has_redsec_stats(pid, nid, candidate.get('platform', 'ea')):
                        return pid, nid
        
        # Se nenhuma tiver stats, retorna o primeiro disponível (prioridade: cem_ea > steam/origin > console > qualquer)
        for candidate in [cem_ea, steam_origin, console, personas[0]]:
            if candidate:
                return candidate.get('personaId'), candidate.get('nucleusId')
        
        return None, None
    except Exception:
        return None, None


def resolve_player_ids_with_platform(gamertag: str) -> tuple:
    """
    Igual a resolve_player_ids, mas também retorna a plataforma da conta encontrada.
    Retorna (persona_id, nucleus_id, platform) ou (None, None, None).
    Usado pelo auto-update para corrigir plataformas desatualizadas no banco (ex: 'pc').
    """
    session = make_session()
    try:
        resp = session.get(
            f"https://api.gametools.network/bf6/player?name={gamertag}",
            timeout=30
        )
        if resp.status_code != 200:
            return None, None, None
        personas = resp.json().get('results', [])
        if not personas:
            return None, None, None

        # Separa personas por tipo
        cem_ea = None
        steam_origin = None
        console = None

        for p in personas:
            pid = p.get('platformId')
            if pid == 'cem_ea_id':
                cem_ea = p
            elif pid in ['steam', 'origin']:
                steam_origin = p
            elif pid in ['xbox', 'xboxone', 'ps4', 'ps5']:
                console = p

        # Tenta cada tipo em ordem, verificando se tem stats
        for candidate in [cem_ea, steam_origin, console]:
            if candidate:
                pid  = candidate.get('personaId')
                nid  = candidate.get('nucleusId')
                plat = candidate.get('platform', 'ea')
                if pid and nid:
                    if _has_redsec_stats(pid, nid, plat):
                        return pid, nid, plat

        # Se nenhuma tiver stats, retorna o primeiro disponível
        for candidate in [cem_ea, steam_origin, console, personas[0]]:
            if candidate:
                return candidate.get('personaId'), candidate.get('nucleusId'), candidate.get('platform', 'ea')

        return None, None, None
    except Exception:
        return None, None, None


def _has_redsec_stats(persona_id: str, nucleus_id: str, platform: str) -> bool:
    """Verifica se uma conta tem stats não-zerados no Redsec."""
    session = make_session()
    try:
        url = f"{BASE_STATS_URL}&playerid={persona_id}&nucleus_id={nucleus_id}&platform={platform}"
        resp = session.get(url, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            kd, _ = _extract_redsec_kd(data)
            return kd > 0.0
        return False
    except Exception:
        return False


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


def fetch_stats(gamertag: str, platform: str):
    """
    Busca stats com fallback automático:
    1. Tenta pelo nome + plataforma
    2. Se KD vier zerado ou Redsec não encontrado, busca personaId/nucleusId via /bf6/player
    3. Refaz a busca de stats com os IDs corretos (prioriza cem_ea_id com stats, depois steam/origin, etc)
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

    # --- Tentativa 2: busca personaId/nucleusId via /bf6/player COM FALLBACK ---
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

        # Separa personas por tipo
        cem_ea = None
        steam_origin = None
        console = None
        
        for p in personas:
            pid = p.get('platformId')
            if pid == 'cem_ea_id':
                cem_ea = p
            elif pid in ['steam', 'origin']:
                steam_origin = p
            elif pid in ['xbox', 'xboxone', 'ps4', 'ps5']:
                console = p
        
        # Tenta cada tipo em ordem, buscando a primeira com stats
        for candidate in [cem_ea, steam_origin, console]:
            if candidate:
                persona_id = candidate.get('personaId')
                nucleus_id = candidate.get('nucleusId')
                plat = candidate.get('platform', platform)
                
                if persona_id and nucleus_id:
                    # --- Tentativa 3: stats pelo playerid + nucleus_id ---
                    fixed_url = f"{BASE_STATS_URL}&playerid={persona_id}&nucleus_id={nucleus_id}&platform={plat}"
                    resp2 = session.get(fixed_url, timeout=15)
                    if resp2.status_code == 200:
                        data = resp2.json()
                        kd, _ = _extract_redsec_kd(data)
                        if kd > 0.0:
                            return data  # Encontrou conta com stats!
                    elif resp2.status_code == 500:
                        api_failed = True
        
        # Se chegou aqui, nenhuma conta tem stats — retorna None
        return None

    except Exception:
        api_failed = True

    return "api_error" if api_failed else None
