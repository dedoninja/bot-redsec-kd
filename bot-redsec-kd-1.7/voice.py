import asyncio
import time
import discord
from datetime import datetime, timezone, timedelta
from config import (
    SERVER_ID,
    VOICE_TRIGGER_MAP,
    VOICE_PROTECTED_CHANNELS,
    VOICE_TARGET_CATEGORIES,
    VOICE_MANAGE_CHANNEL_CATEGORIES,
    VOICE_COOLDOWN_SECONDS,
    LOGS_CHANNEL_ID,
)

# Rastreia salas criadas pelo bot em memória
_temp_voice_channels: set[int] = set()
_voice_cooldowns: dict[int, float] = {}   # user_id → timestamp do último processamento


async def handle_voice_state_update(bot: discord.Bot, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    """Lógica principal do on_voice_state_update."""
    if member.guild.id != SERVER_ID:
        return

    # ── Entrou num canal de criação ──────────────────────────────────────────
    if after.channel and after.channel.id in VOICE_TRIGGER_MAP:
        # Verificação de ban antes de criar sala
        from commands.banlist import is_banned, get_ban_reason
        if is_banned(member.id, "voice"):
            motivo = get_ban_reason(member.id, "voice")
            try:
                await member.send(f"❌ Você está banido de criar salas temporárias.\nMotivo: {motivo}")
            except Exception:
                pass

            # Desconecta o usuário do canal de voz
            try:
                await member.move_to(None)
            except Exception as e:
                print(f"[VOICE] Erro ao tentar desconectar o usuário banido {member.name}: {e}")

            return

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
            manage_channels=category_id in VOICE_MANAGE_CHANNEL_CATEGORIES,
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
        channel   = before.channel
        in_memory = channel.id in _temp_voice_channels
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
            except discord.NotFound:
                # Sala já foi removida (ex: pela varredura periódica) — não é um erro real
                pass
            except Exception as e:
                print(f"[VOICE] Erro ao deletar sala: {e}")
            finally:
                _temp_voice_channels.discard(channel.id)


async def voice_sweep_loop(bot: discord.Bot):
    await bot.wait_until_ready()
    FUSO_BRASILIA         = timezone(timedelta(hours=-3))
    SWEEP_INTERVALO_HORAS = 4   # <- intervalo entre varreduras (em horas); ajuste aqui se necessario

    while not bot.is_closed():
        try:
            agora = datetime.now(FUSO_BRASILIA)
            # Calcula o proximo horario multiplo do intervalo (ex: 00:00, 04:00, 08:00, ...)
            hora_atual     = agora.hour + agora.minute / 60 + agora.second / 3600
            horas_passadas = hora_atual % SWEEP_INTERVALO_HORAS
            horas_espera   = SWEEP_INTERVALO_HORAS - horas_passadas
            proximo        = agora + timedelta(hours=horas_espera)
            proximo        = proximo.replace(minute=0, second=0, microsecond=0)
            espera         = (proximo - agora).total_seconds()
            print(f"[VOICE-SWEEP] Proxima varredura as {proximo.strftime('%d/%m/%Y %H:%M')} (Brasilia). Aguardando {espera/3600:.1f}h.")
            await asyncio.sleep(espera)
            salas_deletadas, nomes_deletados = await run_voice_sweep(bot)
            # Reporta no canal de logs se deletou salas
            if salas_deletadas > 0:
                logs_ch = bot.get_channel(LOGS_CHANNEL_ID)
                if logs_ch:
                    lista = "\n".join(f"- {nome}" for nome in nomes_deletados)
                    await logs_ch.send(f"🧹 Varredura {proximo.strftime('%H:%M')} — **{salas_deletadas}** sala(s) de voz vazia(s) removida(s).\n{lista}")
        except Exception as e:
            print(f"[VOICE-SWEEP] Erro no loop: {e}")
            await asyncio.sleep(60)


async def run_voice_sweep(bot: discord.Bot) -> tuple[int, list[str]]:
    print(f"[VOICE-SWEEP] Iniciando varredura - {datetime.utcnow().isoformat()}")
    guild = bot.get_guild(SERVER_ID)
    if not guild:
        print("[VOICE-SWEEP] Servidor não encontrado.")
        return 0, []

    deletados = 0
    nomes_deletados: list[str] = []
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
            nome = channel.name
            try:
                await channel.delete(reason="Varredura — sala vazia")
                deletados += 1
                nomes_deletados.append(nome)
            except discord.Forbidden:
                print(f"[VOICE-SWEEP] Sem permissão para deletar '{nome}'")
            except Exception:
                pass
            finally:
                _temp_voice_channels.discard(channel.id)

    print(f"[VOICE-SWEEP] Concluída. Salas removidas: {deletados}")
    return deletados, nomes_deletados
