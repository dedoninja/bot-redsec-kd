import asyncio
import discord
from datetime import datetime, timezone, timedelta
from config import (
    SERVER_ID, LOGS_CHANNEL_ID,
    DEDO_USER_ID, ROLE_FAZENDEIRO,
    KD_ROLES, SUSPEITA_ROLES, BASE_STATS_URL,
)
from database import load_users, save_users
from api import make_session, make_links, fetch_stats, resolve_player_ids, resolve_player_ids_with_platform, extract_ids_from_stats
from utils import extract_kd_and_human, apply_roles
from voice import handle_voice_state_update, voice_sweep_loop
from commands.admin import RegisterView, TrocaGametagView

async def on_ready(bot: discord.Bot):
    from commands.admin import RegisterView, TrocaGametagView
    print(f'{bot.user} online!')
    bot.add_view(RegisterView(bot))
    bot.add_view(TrocaGametagView(bot))
    try:
        await bot.sync_commands()
        print('Comandos slash sincronizados.')
    except Exception as e:
        print(f'Erro ao sincronizar comandos: {e}')

    bot.loop.create_task(auto_update_loop(bot))
    bot.loop.create_task(voice_sweep_loop(bot))


async def on_voice_state_update(bot: discord.Bot, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    await handle_voice_state_update(bot, member, before, after)


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


# ================== LOOP AUTO-UPDATE ==================

async def auto_update_loop(bot: discord.Bot):
    await bot.wait_until_ready()
    HORARIO_UPDATE = 4  # 04:00 Brasília
    FUSO_BRASILIA  = timezone(timedelta(hours=-3))

    while not bot.is_closed():
        try:
            agora   = datetime.now(FUSO_BRASILIA)
            proximo = agora.replace(hour=HORARIO_UPDATE, minute=0, second=0, microsecond=0)
            if agora >= proximo:
                proximo += timedelta(days=1)
            espera  = (proximo - agora).total_seconds()
            print(f"[AUTO-UPDATE] Próximo update às {proximo.strftime('%d/%m/%Y %H:%M')} (Brasília). Aguardando {espera/3600:.1f}h.")
            await asyncio.sleep(espera)
            await run_auto_update(bot)

        except Exception as e:
            print(f"[AUTO-UPDATE] Erro no loop: {e}")
            await asyncio.sleep(60)
            continue

        # Chama atualização do Top 5 após o auto-update (se módulo registrado)
        # Executado fora do try/except do auto-update para não ser suprimido por erros
        if hasattr(bot, "top5_update"):
            try:
                await bot.top5_update(bot)
            except Exception as e:
                print(f"[TOP5] Erro na atualização diária: {e}")


# ================== RUN AUTO-UPDATE ==================

async def run_auto_update(bot: discord.Bot):
    print(f"[AUTO-UPDATE] Iniciando - {datetime.utcnow().isoformat()}")
    guild = bot.get_guild(SERVER_ID)
    if not guild:
        print("[AUTO-UPDATE] Servidor não encontrado.")
        return

    users = load_users()
    if not users:
        print("[AUTO-UPDATE] Nenhum usuário registrado.")
        return

    total         = len(users)
    updated       = 0
    failed        = 0
    sus_alerts    = []   # Human% baixo detectado
    fail_details  = []   # Detalhes de falhas
    removed_users = {}   # Usuários que saíram do servidor

    for discord_id, info in list(users.items()):
        gamertag   = info.get('gamertag')
        platform   = info.get('platform', 'ea')

        try:
            member = guild.get_member(int(discord_id))
            if not member:
                print(f"[AUTO-UPDATE] Membro {discord_id} não está no servidor, removendo do JSON.")
                removed_users[discord_id] = info
                continue

            old_kd_roles = [r for r in member.roles if r.id in KD_ROLES]

            persona_id = info.get('persona_id')
            nucleus_id = info.get('nucleus_id')

            # Se tiver IDs salvos, usa direto sem passar pelo /bf6/player
            if persona_id and nucleus_id:
                # Não inclui platform=pc pois não é mais válido na API; omitir é mais seguro
                if platform == 'pc':
                    fixed_url = f"{BASE_STATS_URL}&playerid={persona_id}&nucleus_id={nucleus_id}"
                else:
                    fixed_url = f"{BASE_STATS_URL}&playerid={persona_id}&nucleus_id={nucleus_id}&platform={platform}"
                session   = make_session()
                try:
                    resp = session.get(fixed_url, timeout=15)
                    data = resp.json() if resp.status_code == 200 else None
                    if data is None:
                        data = "api_error" if resp.status_code == 500 else None
                except Exception:
                    data = "api_error"
                
                # ✅ NOVO: Se data veio OK mas KD está zerado, tenta fallback por nome
                if data and data != "api_error":
                    from utils import extract_kd_and_human as check_kd
                    kd_check, _ = check_kd(data)
                    # Corrige plataforma desatualizada (ex: 'pc') aproveitando a passagem
                    if platform == 'pc' and kd_check > 0.0:
                        pid_r, nid_r, plat_resolved = await asyncio.to_thread(resolve_player_ids_with_platform, gamertag)
                        if plat_resolved and plat_resolved != 'pc':
                            print(f"[AUTO-UPDATE] {gamertag} — Plataforma corrigida: pc → {plat_resolved}")
                            users[discord_id]['platform'] = plat_resolved
                            save_users(users)
                    if kd_check == 0.0:
                        print(f"[AUTO-UPDATE] {gamertag} — IDs salvos retornaram KD 0.00, tentando fallback por nome...")
                        data_fallback = await asyncio.to_thread(fetch_stats, gamertag, platform)
                        if data_fallback and data_fallback != "api_error":
                            kd_fallback, _ = check_kd(data_fallback)
                            if kd_fallback > 0.0:
                                # Encontrou conta com stats! Atualiza IDs no JSON
                                print(f"[AUTO-UPDATE] {gamertag} — Fallback bem-sucedido! KD: {kd_fallback:.2f}")
                                data = data_fallback
                                # Atualiza os IDs e plataforma no JSON para próximas vezes
                                pid, nid, plat_resolved = await asyncio.to_thread(resolve_player_ids_with_platform, gamertag)
                                if pid and nid:
                                    users[discord_id]['persona_id'] = pid
                                    users[discord_id]['nucleus_id']  = nid
                                    if plat_resolved and users[discord_id].get('platform') != plat_resolved:
                                        print(f"[AUTO-UPDATE] {gamertag} — Plataforma atualizada: {users[discord_id].get('platform')} → {plat_resolved}")
                                        users[discord_id]['platform'] = plat_resolved
                                    save_users(users)
            else:
                data = await asyncio.to_thread(fetch_stats, gamertag, platform)
                # Se conseguiu dados, extrai IDs do próprio JSON de stats (não depende do /bf6/player)
                if data and data != "api_error":
                    pid, nid = extract_ids_from_stats(data)
                    if not (pid and nid):
                        # Fallback via /bf6/player se não veio no JSON
                        pid, nid, plat_resolved = await asyncio.to_thread(resolve_player_ids_with_platform, gamertag)
                    else:
                        plat_resolved = data.get('platform', platform)
                    if pid and nid:
                        users[discord_id]['persona_id'] = pid
                        users[discord_id]['nucleus_id']  = nid
                        if plat_resolved and users[discord_id].get('platform') != plat_resolved:
                            print(f"[AUTO-UPDATE] {gamertag} — Plataforma atualizada: {users[discord_id].get('platform')} → {plat_resolved}")
                            users[discord_id]['platform'] = plat_resolved
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

            changes  = await apply_roles(member, guild, kd_val, human_pct)
            updated += 1

            new_kd_roles = [r for r in member.roles if r.id in KD_ROLES]
            kd_changed   = set(r.id for r in old_kd_roles) != set(r.id for r in new_kd_roles)
            is_sus       = changes['suspeita_interno'] not in ["Honesto", "Human% indisponível"]

            if is_sus:
                fazendeiro_role = member.guild.get_role(ROLE_FAZENDEIRO)
                is_fazendeiro   = fazendeiro_role and fazendeiro_role in member.roles
                if not is_fazendeiro:
                    sus_alerts.append(
                        f"- {member.mention} (`{gamertag}` | {platform}) | "
                        f"KD: **{kd_val:.2f}** | ⚠️ Human%: **{human_pct:.2f}%** → **{changes['suspeita_interno']}** | "
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
