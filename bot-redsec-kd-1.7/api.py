import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from config import BASE_STATS_URL, BASE_PROFILE_URL


def make_session() -> requests.Session:
    session = requests.Session()
    retries = Retry(total=1, backoff_factor=1, status_forcelist=[502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retries))
    return session


def make_links(gamertag: str, platform: str, persona_id: str = None, nucleus_id: str = None) -> str:
    """Gera links clicáveis [Stats] e [JSON] sem thumbnail para uso nos canais de log/ADM."""
    if nucleus_id:
        stats_link = f"[Stats](<https://battlefield.joarchy.com/p/{nucleus_id}>)"
    else:
        stats_link = f"[Stats](<https://gametools.network/stats/{platform}/name/{gamertag}?game=bf6>)"
    if persona_id and nucleus_id:
        json_url = f"https://api.gametools.network/bf6/stats/?playerid={persona_id}&nucleus_id={nucleus_id}"
    else:
        json_url = f"https://api.gametools.network/bf6/stats/?name={gamertag}"
    json_link = f"[JSON](<{json_url}>)"
    return f"{stats_link} | {json_link}"


def resolve_player_ids(gamertag: str, session: requests.Session = None) -> tuple:
    """
    Busca personaId e nucleusId via /bf6/player. Retorna (persona_id, nucleus_id) ou (None, None).
    
    NOVA LÓGICA COM FALLBACK:
    1. Prioriza cem_ea_id
    2. Se cem_ea_id tiver KD 0.00, busca steam/origin
    3. Se steam/origin também zerado, busca xbox/psn
    4. Se todos zerados, retorna o primeiro cem_ea_id mesmo assim

    Aceita session opcional para reutilizar a sessão do caller e evitar vazamento.
    """
    _own_session = session is None
    if _own_session:
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
                    # Verifica se essa conta tem stats no Redsec (reutiliza session)
                    if _has_redsec_stats(pid, nid, candidate.get('platform', 'ea'), session=session):
                        return pid, nid
        
        # Se nenhuma tiver stats, retorna o primeiro disponível (prioridade: cem_ea > steam/origin > console > qualquer)
        for candidate in [cem_ea, steam_origin, console, personas[0]]:
            if candidate:
                return candidate.get('personaId'), candidate.get('nucleusId')
        
        return None, None
    except Exception:
        return None, None
    finally:
        if _own_session:
            try:
                session.close()
            except Exception:
                pass


def resolve_player_ids_with_platform(gamertag: str, session: requests.Session = None) -> tuple:
    """
    Igual a resolve_player_ids, mas também retorna a plataforma da conta encontrada.
    Retorna (persona_id, nucleus_id, platform) ou (None, None, None).
    Usado pelo auto-update para corrigir plataformas desatualizadas no banco (ex: 'pc').

    Aceita session opcional para reutilizar a sessão do caller e evitar vazamento.
    """
    _own_session = session is None
    if _own_session:
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
                    # Reutiliza session para não abrir nova conexão
                    if _has_redsec_stats(pid, nid, plat, session=session):
                        return pid, nid, plat

        # Se nenhuma tiver stats, retorna o primeiro disponível
        for candidate in [cem_ea, steam_origin, console, personas[0]]:
            if candidate:
                return candidate.get('personaId'), candidate.get('nucleusId'), candidate.get('platform', 'ea')

        return None, None, None
    except Exception:
        return None, None, None
    finally:
        if _own_session:
            try:
                session.close()
            except Exception:
                pass


def _has_redsec_stats(persona_id: str, nucleus_id: str, platform: str, session: requests.Session = None) -> bool:
    """Verifica se uma conta tem stats não-zerados no Redsec.

    Aceita session opcional para reutilizar a sessão do caller e evitar vazamento.
    """
    _own_session = session is None
    if _own_session:
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
    finally:
        if _own_session:
            try:
                session.close()
            except Exception:
                pass


def _extract_redsec_kd(data: dict) -> tuple:
    """Auxiliar: extrai apenas o KD do Redsec para decisão de fallback.

    LÓGICA ATUAL: usa o killDeath do grupo 'Battle Royale' em gameModeGroups.
    Fallback para gameModes caso gameModeGroups não tenha Battle Royale.
    """
    # Prioridade: gameModeGroups com gamemodeName == 'Battle Royale'
    for group in data.get('gameModeGroups', []):
        if group.get('gamemodeName') == 'Battle Royale':
            try:
                kd = float(group.get('killDeath', 0.0))
            except (ValueError, TypeError):
                kd = 0.0
            return kd, True

    # Fallback: gameModes com gamemodeName == 'Battle Royale'
    for mode in data.get('gameModes', []):
        if mode.get('gamemodeName') == 'Battle Royale':
            try:
                kd = float(mode.get('killDeath', 0.0))
            except (ValueError, TypeError):
                kd = 0.0
            return kd, True

    return 0.0, False


def fetch_competitive_rank(persona_id: str, nucleus_id: str, session: requests.Session = None) -> tuple:
    """Busca o rank competitivo mais recente do jogador via /bf6/profile/.

    Retorna (rank: int, rank_name: str) com base no último item de 'competitiveRanks'.

    Distinção importante:
    - Perfil privado: API não retorna 'playerProfiles' no root (retorna 'other' ou vazio).
      → Retorna (0, 'Perfil Privado')
    - Perfil público sem rank (Unranked): 'competitiveRanks' presente, rankName='Unranked', rank=0.
      → Retorna (0, 'Unranked')
    - Sem persona_id/nucleus_id ou erro de API:
      → Retorna (0, 'Perfil Privado') por segurança (não é possível determinar)

    Aceita session opcional para reutilizar a sessão do caller e evitar vazamento.
    """
    if not (persona_id and nucleus_id):
        return 0, 'Perfil Privado'
    _own_session = session is None
    if _own_session:
        session = make_session()
    try:
        url  = f"{BASE_PROFILE_URL}?playerid={persona_id}&nucleus_id={nucleus_id}"
        resp = session.get(url, timeout=15)
        if resp.status_code != 200:
            return 0, 'Perfil Privado'
        data = resp.json()
        profiles = data.get('playerProfiles', [])
        if not profiles:
            # Perfil privado: API retorna 'other' ao invés de 'playerProfiles'
            return 0, 'Perfil Privado'
        # Pega o primeiro perfil (único retornado normalmente)
        profile = profiles[0]
        comp_ranks = profile.get('competitiveRanks', [])
        if not comp_ranks:
            # Perfil público mas sem histórico de rank competitivo
            return 0, 'Perfil Privado'
        # Pega o último item (season mais recente)
        latest = comp_ranks[-1]
        rank      = int(latest.get('rank', 0) or 0)
        rank_name = latest.get('rankName', '') or 'Unranked'
        return rank, rank_name
    except Exception:
        return 0, 'Perfil Privado'
    finally:
        if _own_session:
            try:
                session.close()
            except Exception:
                pass


def extract_ids_from_stats(data: dict) -> tuple:
    """Extrai personaId e nucleusId diretamente da resposta do /bf6/stats/.
    O JSON de stats já contém 'id' (personaId) e 'userId' (nucleusId) no raiz.
    Retorna (persona_id, nucleus_id) ou (None, None).
    """
    try:
        persona_id = str(data.get('id', '')) or None
        nucleus_id = str(data.get('userId', '')) or None
        return persona_id, nucleus_id
    except Exception:
        return None, None


def fetch_stats(gamertag: str, platform: str, persona_id: str = None, nucleus_id: str = None, session: requests.Session = None):
    """
    Busca stats com fallback automático:
    0. Se persona_id+nucleus_id fornecidos, tenta direto (mais confiável)
    1. Tenta pelo nome + plataforma
    2. Se KD vier zerado ou Redsec não encontrado, busca personaId/nucleusId via /bf6/player
    3. Refaz a busca de stats com os IDs corretos
    Retorna:
      - dict       → sucesso
      - None       → jogador não encontrado
      - "api_error" → instabilidade na API de stats (erro 500 ou falha de conexão)

    Aceita session opcional para reutilizar a sessão do caller e evitar vazamento.
    """
    _own_session = session is None
    if _own_session:
        session = make_session()

    api_failed = False       # Sinaliza erro de infraestrutura (500 / timeout)
    first_valid_data = None  # Primeiro resultado 200 com dados válidos (mesmo KD=0)

    try:
        # --- Tentativa 0: pelos IDs salvos no banco (mais direto e confiável) ---
        if persona_id and nucleus_id:
            try:
                plat_param = "" if platform == "pc" else f"&platform={platform}"
                url0 = f"{BASE_STATS_URL}&playerid={persona_id}&nucleus_id={nucleus_id}{plat_param}"
                resp0 = session.get(url0, timeout=15)
                if resp0.status_code == 200:
                    data0 = resp0.json()
                    first_valid_data = data0
                    kd0, _ = _extract_redsec_kd(data0)
                    if kd0 > 0.0:
                        return data0  # Sucesso com IDs do banco
                    # KD zerado — continua para tentar por nome
                elif resp0.status_code == 500:
                    api_failed = True
            except Exception:
                api_failed = True

        # --- Tentativa 1: pelo nome + plataforma ---
        try:
            url = f"{BASE_STATS_URL}&name={gamertag}&platform={platform}"
            resp = session.get(url, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                first_valid_data = data
                kd, _ = _extract_redsec_kd(data)
                if kd > 0.0:
                    return data  # Sucesso direto com KD Redsec
            elif resp.status_code == 500:
                api_failed = True
        except Exception:
            api_failed = True

        # --- Tentativa 2: resolve personaId/nucleusId via /bf6/player ---
        try:
            player_resp = session.get(
                f"https://api.gametools.network/bf6/player?name={gamertag}",
                timeout=30
            )
            if player_resp.status_code != 200:
                if player_resp.status_code == 500:
                    api_failed = True
                # Retorna o que tiver: dados da T1 (KD=0), api_error ou None
                if first_valid_data is not None:
                    return first_valid_data
                return "api_error" if api_failed else None

            personas = player_resp.json().get('results', [])
            if not personas:
                # Player lookup OK mas sem resultados — confia no que a T1 retornou
                if first_valid_data is not None:
                    return first_valid_data
                return None

            # Separa personas por tipo de plataforma
            cem_ea       = None
            steam_origin = None
            console      = None

            for p in personas:
                pid = p.get('platformId')
                if pid == 'cem_ea_id':
                    cem_ea = p
                elif pid in ['steam', 'origin']:
                    steam_origin = p
                elif pid in ['xbox', 'xboxone', 'ps4', 'ps5']:
                    console = p

            # --- Tentativa 3: stats por playerid+nucleus_id para cada candidato ---
            for candidate in [cem_ea, steam_origin, console]:
                if not candidate:
                    continue
                persona_id = candidate.get('personaId')
                nucleus_id = candidate.get('nucleusId')
                plat       = candidate.get('platform', platform)

                if not (persona_id and nucleus_id):
                    continue

                fixed_url = f"{BASE_STATS_URL}&playerid={persona_id}&nucleus_id={nucleus_id}&platform={plat}"
                try:
                    resp2 = session.get(fixed_url, timeout=15)
                    if resp2.status_code == 200:
                        data = resp2.json()
                        if first_valid_data is None:
                            first_valid_data = data  # Guarda como fallback
                        kd, _ = _extract_redsec_kd(data)
                        if kd > 0.0:
                            return data  # Conta com stats Redsec encontrada
                    elif resp2.status_code == 500:
                        api_failed = True
                except Exception:
                    api_failed = True

            # Nenhum candidato tem KD Redsec > 0
            # Retorna o primeiro 200 válido (jogador existe mas sem partidas Redsec)
            if first_valid_data is not None:
                return first_valid_data
            return "api_error" if api_failed else None

        except Exception:
            api_failed = True

        if first_valid_data is not None:
            return first_valid_data
        return "api_error" if api_failed else None

    finally:
        if _own_session:
            try:
                session.close()
            except Exception:
                pass
