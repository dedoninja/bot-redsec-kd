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
        json_url = f"https://api.gametools.network/bf6/stats/?playerid={persona_id}&nucleus_id={nucleus_id}&platform={platform}"
    else:
        json_url = f"https://api.gametools.network/bf6/stats/?name={gamertag}&platform={platform}"
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
