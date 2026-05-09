import discord
import logging
import asyncio
from flask import Flask, redirect
from threading import Thread

from config import TOKEN, GITHUB_PAGE_URL
from events import (
    on_ready                     as _on_ready,
    on_voice_state_update        as _on_voice_state_update,
    on_application_command_error as _on_application_command_error,
)
from commands.kd          import setup_kd
from commands.stats       import setup_stats
from commands.minha_conta import setup_minha_conta
from commands.ajuda       import setup_ajuda
from commands.suspeitos   import setup_suspeitos
from commands.admin       import setup_admin
from commands.top5        import setup_top5
from commands.banlist     import setup_banlist
from commands.duplicados  import setup_duplicados
from commands.voice_ban   import setup_voice_ban

# ================== FLASK DUMMY ==================
app = Flask(__name__)

@app.route('/')
def home():
    return redirect(GITHUB_PAGE_URL)

@app.route('/favicon.ico')
def favicon():
    return redirect("https://cdn.discordapp.com/app-icons/1477325845277184112/6a7d1d2360e2cfcb656f221e6b00f908.png")

def run_flask():
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    app.run(host='0.0.0.0', port=8080)

Thread(target=run_flask, daemon=True).start()

# ==================== BOT ====================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

def create_bot():
    """Cria uma nova instância do bot e registra eventos/comandos."""
    bot = discord.Bot(intents=intents)

    @bot.event
    async def on_ready():
        await _on_ready(bot)

    @bot.event
    async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        await _on_voice_state_update(bot, member, before, after)

    @bot.event
    async def on_application_command_error(ctx: discord.ApplicationContext, error: discord.DiscordException):
        await _on_application_command_error(ctx, error)

    setup_kd(bot)
    setup_stats(bot)
    setup_minha_conta(bot)
    setup_ajuda(bot)
    setup_suspeitos(bot)
    setup_admin(bot)
    setup_top5(bot)
    setup_banlist(bot)
    setup_duplicados(bot)
    setup_voice_ban(bot)

    return bot

# ================== INICIALIZAÇÃO COM RETRY ==================
async def run_bot_with_retry():
    """
    Executa o bot com retry automático em caso de falha na API do Discord.
    Usa backoff exponencial: 30s -> 60s -> 120s -> 240s -> máximo 300s.
    """
    tentativa = 0
    delay_base = 30      # segundos iniciais de espera
    delay_max  = 300     # máximo 5 minutos entre tentativas

    while True:
        bot = create_bot()
        try:
            print(f"[BOT] Tentando conectar... (tentativa #{tentativa + 1})")
            await bot.start(TOKEN)

        except discord.errors.HTTPException as e:
            # Erros HTTP da API do Discord (429, 503, 504, etc.)
            tentativa += 1
            delay = min(delay_base * (2 ** (tentativa - 1)), delay_max)
            print(f"[BOT] Erro HTTP da API do Discord: {e.status} {e.text}")
            print(f"[BOT] Aguardando {delay}s antes de reconectar...")
            await asyncio.sleep(delay)

        except discord.errors.ConnectionClosed as e:
            # Conexão WebSocket encerrada pelo Discord
            tentativa += 1
            delay = min(delay_base * (2 ** (tentativa - 1)), delay_max)
            print(f"[BOT] Conexão encerrada pelo Discord (código {e.code}): {e.reason}")
            print(f"[BOT] Aguardando {delay}s antes de reconectar...")
            await asyncio.sleep(delay)

        except discord.errors.GatewayNotFound:
            # Gateway do Discord indisponível
            tentativa += 1
            delay = min(delay_base * (2 ** (tentativa - 1)), delay_max)
            print(f"[BOT] Gateway do Discord não encontrado.")
            print(f"[BOT] Aguardando {delay}s antes de reconectar...")
            await asyncio.sleep(delay)

        except Exception as e:
            # Qualquer outro erro inesperado — loga e tenta novamente
            tentativa += 1
            delay = min(delay_base * (2 ** (tentativa - 1)), delay_max)
            print(f"[BOT] Erro inesperado: {type(e).__name__}: {e}")
            print(f"[BOT] Aguardando {delay}s antes de reconectar...")
            await asyncio.sleep(delay)

        else:
            # bot.start() encerrou sem exceção (desconexão limpa)
            print("[BOT] Desconectado. Reconectando em 30s...")
            tentativa = 0
            await asyncio.sleep(30)

        finally:
            # Garante que o bot feche a sessão HTTP antes de recriar
            try:
                if not bot.is_closed():
                    await bot.close()
            except Exception:
                pass

asyncio.run(run_bot_with_retry())
