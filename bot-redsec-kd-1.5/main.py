import discord
import logging
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

bot = discord.Bot(intents=intents)

# ================== REGISTRO DE EVENTOS ==================
@bot.event
async def on_ready():
    await _on_ready(bot)

@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    await _on_voice_state_update(bot, member, before, after)

@bot.event
async def on_application_command_error(ctx: discord.ApplicationContext, error: discord.DiscordException):
    await _on_application_command_error(ctx, error)

# ================== REGISTRO DE COMANDOS ==================
setup_kd(bot)
setup_stats(bot)
setup_minha_conta(bot)
setup_ajuda(bot)
setup_suspeitos(bot)
setup_admin(bot)
setup_top5(bot)
setup_banlist(bot)
setup_duplicados(bot)

# ================== INICIALIZAÇÃO ==================
bot.run(TOKEN)
