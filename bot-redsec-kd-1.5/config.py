import os

# ==================== TOKEN ====================
TOKEN = os.getenv('TOKEN')

# ==================== SERVIDOR ====================
SERVER_ID           = 405506950562840577
REGISTER_CHANNEL_ID = 1486425299502764105
BOT_SPAM_CHANNEL_ID = 869818537793966090

# ==================== ROLES DE KD ====================
ROLE_KD2 = 1477322781774450868
ROLE_KD3 = 1477322769825005599
ROLE_KD4 = 1477322732201971945
ROLE_KD5 = 1477322675612553296
KD_ROLES = [ROLE_KD2, ROLE_KD3, ROLE_KD4, ROLE_KD5]

# ==================== CANAIS E ROLES ADMIN ====================
ADM_CHAT_CHANNEL_ID       = 405658596051779584
ADM_COMMANDS_CHANNEL_ID   = 405665188566532097  # Canal de comandos admin (testes)
LOGS_CHANNEL_ID           = 1487221094174818495
TROCA_GAMETAG_CHANNEL_ID  = 1495131590131716138  # Canal de solicitações de troca de ID
RULES_CHANNEL_ID          = 459487274346872833   # Canal de regras do servidor
STAFF_ROLE_ID             = 472110979790929922
DEDO_USER_ID              = 84299190288523264

# ==================== SALAS TEMPORÁRIAS ====================

# Canais de criação → (categoria destino, nome da sala)
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

# Categorias monitoradas pela varredura de salas vazias
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

VOICE_COOLDOWN_SECONDS = 5

# ==================== GIFs E URLs ====================
GIF_EA_ID    = "https://i.imgur.com/8hmECSV.gif"
GIF_DataShare = "https://i.imgur.com/2Qp2qAI.gif"
GITHUB_PAGE_URL = "https://dedoninja.github.io/bot-redsec-kd/"

# ==================== API ====================
BASE_STATS_URL = (
    "https://api.gametools.network/bf6/stats/"
    "?raw=false&format_values=true"
    "&skip_battlelog=true"
)

# ==================== BANCO DE DADOS ====================
DATA_DIR  = "/data" if os.path.exists("/data") else os.path.join(os.path.dirname(__file__), "data")
DATA_FILE = os.path.join(DATA_DIR, "users.json")

# ==================== BANLIST ====================
BANS_FILE = os.path.join(DATA_DIR, "bans.json")

# Tipos de ban suportados
BAN_TYPES = {
    "voice": "banido de criar salas temporárias",
    "register": "banido de se registrar no bot",
    "commands": "banido de usar comandos slash"
}