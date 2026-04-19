import discord
from discord.ui import Button, View, Modal, InputText
from database import load_users
from config import TROCA_GAMETAG_CHANNEL_ID


class TrocaGametagModal(Modal):
    def __init__(self, bot: discord.Bot):
        super().__init__(title="Solicitar troca de ID")
        self._bot = bot

        self.add_item(InputText(label="Novo ID EA", required=True, max_length=64))
        self.add_item(InputText(label="Nova Plataforma (pc, psn ou xbox)", required=True, max_length=4))
        self.add_item(InputText(label="Motivo da troca de ID", style=discord.InputTextStyle.long, required=True, max_length=500))

    async def callback(self, interaction: discord.Interaction):
        bot = self._bot

        nova_gametag = self.children[0].value.strip()
        nova_plataforma = self.children[1].value.strip().lower()
        motivo = self.children[2].value.strip()

        if nova_plataforma not in ['pc', 'psn', 'xbox']:
            await interaction.response.send_message("❌ Plataforma inválida.", ephemeral=True)
            return

        users = load_users()
        discord_id = str(interaction.user.id)
        current_data = users.get(discord_id)

        if not current_data:
            await interaction.response.send_message("❌ Você não está cadastrado.", ephemeral=True)
            return

        gametag_atual = current_data.get('gamertag', 'N/A')
        plataforma_atual = current_data.get('platform', 'N/A')

        troca_channel = bot.get_channel(TROCA_GAMETAG_CHANNEL_ID)
        if troca_channel:
            view = AprovarTrocaView(bot, interaction.user.id, nova_gametag, nova_plataforma)

            await troca_channel.send(
                f"🔄 **Nova solicitação de troca de ID**\n\n"
                f"**Usuário:** {interaction.user.mention} (`{interaction.user.id}`)\n"
                f"**ID Atual:** `{gametag_atual}` | `{plataforma_atual}`\n"
                f"**Nova ID:** `{nova_gametag}` | `{nova_plataforma}`\n"
                f"**Motivo:** {motivo}\n\n"
                f"*Use o botão abaixo ou `/force_register discord_id:{interaction.user.id} gamertag:{nova_gametag} plataforma:{nova_plataforma}` para aprovar a troca.*",
                view=view
            )

        await interaction.response.send_message("✅ Solicitação enviada!", ephemeral=True)


class TrocaGametagView(View):
    def __init__(self, bot: discord.Bot):
        super().__init__(timeout=None)
        self._bot = bot

    @discord.ui.button(label="🔄 Solicitar troca", style=discord.ButtonStyle.green, custom_id="troca_gametag_btn")
    async def troca_button(self, button: Button, interaction: discord.Interaction):
        await interaction.response.send_modal(TrocaGametagModal(self._bot))


# ================== NOVO BOTÃO DE APROVAÇÃO ==================
class AprovarTrocaView(View):
    def __init__(self, bot, discord_id, gamertag, plataforma):
        super().__init__(timeout=None)
        self.bot = bot
        self.discord_id = str(discord_id)
        self.gamertag = gamertag
        self.plataforma = plataforma

    @discord.ui.button(label="✅ Aprovar", style=discord.ButtonStyle.green, custom_id="aprovar_troca_btn")
    async def aprovar(self, button: Button, interaction: discord.Interaction):

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        from commands.admin import force_register_internal

        await force_register_internal(
            bot=self.bot,
            discord_id=self.discord_id,
            gamertag=self.gamertag,
            plataforma=self.plataforma,
            interaction=interaction
        )

        button.label = "Aprovado"
        button.style = discord.ButtonStyle.gray
        button.disabled = True

        await interaction.edit_original_response(view=self)