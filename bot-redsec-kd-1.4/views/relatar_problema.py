import discord
from discord.ui import Button, View, Modal, InputText
from database import load_users
from config import ADM_CHAT_CHANNEL_ID


class RelatarProblemaModal(Modal):
    """Modal para relatar problema com EA ID já cadastrada"""
    def __init__(self, bot: discord.Bot):
        super().__init__(title="Relatar problema com ID")
        self._bot = bot

        self.add_item(InputText(
            label="Qual é o seu ID da EA? (Digite corretamente)",
            placeholder="Ex: Hinachiwar",
            required=True,
            max_length=64
        ))
        self.add_item(InputText(
            label="Plataforma (pc, psn ou xbox)",
            placeholder="pc",
            required=True,
            max_length=4
        ))
        self.add_item(InputText(
            label="Informações extras (opcional)",
            style=discord.InputTextStyle.long,
            required=False,
            max_length=500
        ))

    async def callback(self, interaction: discord.Interaction):
        bot = self._bot
        
        ea_id_relatada = self.children[0].value.strip()
        plataforma_relatada = self.children[1].value.strip().lower()
        info_extra = self.children[2].value.strip() if self.children[2].value else "Nenhuma informação adicional fornecida"

        # Validação de plataforma
        if plataforma_relatada not in ['pc', 'psn', 'xbox']:
            await interaction.response.send_message(
                "❌ Plataforma inválida. Use **pc**, **psn** ou **xbox**.",
                ephemeral=True
            )
            return

        # Buscar no banco quem está usando essa EA ID
        users = load_users()
        usuario_usando = None
        discord_id_usando = None
        
        for disc_id, data in users.items():
            if data.get('gamertag', '').lower() == ea_id_relatada.lower():
                discord_id_usando = disc_id
                usuario_usando = data
                break

        # Enviar relatório para o canal da staff
        staff_channel = bot.get_channel(ADM_CHAT_CHANNEL_ID)
        if staff_channel:
            embed = discord.Embed(
                title="🆔 Relatório de ID Duplicada",
                color=discord.Color.orange(),
                description=f"Um usuário reportou que sua EA ID está sendo usada por outra pessoa no servidor."
            )
            
            # Informações do reclamante
            embed.add_field(
                name="👤 Reclamante",
                value=f"{interaction.user.mention} (`{interaction.user.id}`)",
                inline=False
            )
            
            embed.add_field(
                name="🎮 EA ID Relatada",
                value=f"`{ea_id_relatada}`",
                inline=True
            )
            
            embed.add_field(
                name="🖥️ Plataforma",
                value=f"`{plataforma_relatada}`",
                inline=True
            )
            
            # Informações de quem está usando a ID
            if usuario_usando and discord_id_usando:
                embed.add_field(
                    name="⚠️ Atualmente cadastrado em",
                    value=f"<@{discord_id_usando}> (`{discord_id_usando}`)\n"
                          f"Plataforma: `{usuario_usando.get('platform', 'N/A')}`\n"
                          f"Cadastrado em: `{usuario_usando.get('registered_at', 'N/A')[:10]}`",
                    inline=False
                )
            else:
                embed.add_field(
                    name="⚠️ Status",
                    value="EA ID não encontrada no banco de dados atual",
                    inline=False
                )
            
            # Informações extras
            if info_extra != "Nenhuma informação adicional fornecida":
                embed.add_field(
                    name="📝 Informações Extras",
                    value=info_extra,
                    inline=False
                )
            
            embed.set_footer(text="Verifique a veracidade da denúncia antes de tomar ações")
            
            await staff_channel.send(embed=embed)

        # Confirmar ao usuário
        await interaction.response.send_message(
            "📩 Sua solicitação foi enviada para a Staff. Aguarde o contato da equipe.",
            ephemeral=True
        )


class RelatarProblemaView(View):
    """View com botão para abrir o modal de relato"""
    def __init__(self, bot: discord.Bot):
        super().__init__(timeout=None)
        self._bot = bot

    @discord.ui.button(
        label="🆔 Relatar problema",
        style=discord.ButtonStyle.green,
        custom_id="relatar_problema_btn"
    )
    async def relatar_button(self, button: Button, interaction: discord.Interaction):
        await interaction.response.send_modal(RelatarProblemaModal(self._bot))
