import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import asyncio
import os
from collections import deque

# --- KONFIGURASI ---
TOKEN = os.environ['DISCORD_TOKEN']

YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'default_search': 'ytsearch15', # Ambil 15 hasil untuk pagination
    'quiet': True,
}

FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}
ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

# --- STORAGE ---
queues = {}
class MusicQueue:
    def __init__(self):
        self.queue = deque()
        self.current_track = None
        self.loop = False

def get_queue(guild_id):
    if guild_id not in queues: queues[guild_id] = MusicQueue()
    return queues[guild_id]

# --- UI: PAGINATION SEARCH (Halaman 1, 2, 3) ---
class SearchView(discord.ui.View):
    def __init__(self, results, interaction_user):
        super().__init__(timeout=60)
        self.results = results
        self.user = interaction_user
        self.page = 0
        self.per_page = 5

    def create_embed(self):
        start = self.page * self.per_page
        end = start + self.per_page
        current_list = self.results[start:end]
        
        embed = discord.Embed(title="🔍 Hasil Pencarian Music", color=0x2b2d31)
        for i, res in enumerate(current_list):
            durasi = f"{res.get('duration') // 60}:{res.get('duration') % 60:02d}"
            embed.add_field(
                name=f"{start + i + 1}. {res['title'][:60]}",
                value=f"👤 {res['uploader']} | 🕒 {durasi}",
                inline=False
            )
        embed.set_footer(text=f"Halaman {self.page + 1} dari 3")
        return embed

    @discord.ui.button(label="⬅️ Back", style=discord.ButtonStyle.gray)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
            await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="Next ➡️", style=discord.ButtonStyle.gray)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page < 2:
            self.page += 1
            await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="Play Nomor...", style=discord.ButtonStyle.green)
    async def select(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Sederhananya, kita buat dropdown kecil untuk pilih nomor di halaman tsb
        view = discord.ui.View()
        options = []
        start = self.page * self.per_page
        for i in range(start, start + self.per_page):
            options.append(discord.SelectOption(label=f"Lagu {i+1}", value=str(i)))
        
        select_menu = discord.ui.Select(options=options)
        async def select_callback(inter: discord.Interaction):
            idx = int(select_menu.values[0])
            await inter.response.defer()
            await start_playing(inter, self.results[idx]['url'])
        
        select_menu.callback = select_callback
        view.add_item(select_menu)
        await interaction.response.send_message("Pilih nomor lagu:", view=view, ephemeral=True)

# --- UI: MAIN DASHBOARD (Dynamic Buttons) ---
class MusicDashboard(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.button(label="Pause", emoji="⏸️", style=discord.ButtonStyle.secondary)
    async def play_pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc.is_playing():
            vc.pause()
            button.label = "Resume"
            button.emoji = "▶️"
            button.style = discord.ButtonStyle.success
        else:
            vc.resume()
            button.label = "Pause"
            button.emoji = "⏸️"
            button.style = discord.ButtonStyle.secondary
        
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Skip", emoji="⏭️", style=discord.ButtonStyle.primary)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild.voice_client:
            interaction.guild.voice_client.stop()
            await interaction.response.send_message("⏭️ Lagu dilewati!", ephemeral=True)

    @discord.ui.button(label="Volume", emoji="🔊", style=discord.ButtonStyle.gray)
    async def volume_control(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Menu Volume Tambahan
        vol_view = discord.ui.View()
        def create_vol_btn(label, val):
            btn = discord.ui.Button(label=label)
            async def callback(inter: discord.Interaction):
                vc = inter.guild.voice_client
                vc.source.volume = val
                await inter.response.send_message(f"🔊 Volume set ke {int(val*100)}%", ephemeral=True)
            btn.callback = callback
            return btn
        
        vol_view.add_item(create_vol_btn("Low", 0.2))
        vol_view.add_item(create_vol_btn("Mid", 0.5))
        vol_view.add_item(create_vol_btn("High", 0.9))
        await interaction.response.send_message("Pilih Level Volume:", view=vol_view, ephemeral=True)

    @discord.ui.button(label="Stop", emoji="🛑", style=discord.ButtonStyle.danger)
    async def stop_bot(self, interaction: discord.Interaction, button: discord.ui.Button):
        get_queue(self.guild_id).queue.clear()
        await interaction.guild.voice_client.disconnect()
        await interaction.response.edit_message(content="🛑 Pemutaran dihentikan.", embed=None, view=None)

# --- LOGIKA CORE & COMMANDS ---
# (Fungsi start_playing dan play_next tetap stabil seperti sebelumnya)
# Sertakan fungsi pencarian yt_dlp untuk pagination

@bot.tree.command(name="play", description="Cari lagu dengan sistem navigasi halaman")
async def play(interaction: discord.Interaction, search: str):
    await interaction.response.defer()
    
    # Cek koneksi VC
    if not interaction.guild.voice_client:
        await interaction.user.voice.channel.connect()

    # Ambil 15 hasil pencarian
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, lambda: ytdl.extract_info(f"ytsearch15:{search}", download=False))
    
    if not data['entries']:
        return await interaction.followup.send("Lagu tidak ditemukan.")

    view = SearchView(data['entries'], interaction.user)
    await interaction.followup.send(embed=view.create_embed(), view=view)
        
