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
    'default_search': 'ytsearch15',
    'quiet': True,
    'nocheckcertificate': True,
}
FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}
ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

# --- DATA STORAGE ---
queues = {}
class MusicQueue:
    def __init__(self):
        self.queue = deque()
        self.current_track = None
        self.loop = False

def get_queue(guild_id):
    if guild_id not in queues: queues[guild_id] = MusicQueue()
    return queues[guild_id]

# --- UI: SEARCH PAGINATION ---
class SearchView(discord.ui.View):
    def __init__(self, results):
        super().__init__(timeout=60)
        self.results = results
        self.page = 0

    def create_embed(self):
        start = self.page * 5
        current_list = self.results[start:start+5]
        embed = discord.Embed(title="🔍 Hasil Pencarian", color=0x2b2d31)
        for i, res in enumerate(current_list):
            dur = f"{res.get('duration')//60}:{res.get('duration')%60:02d}"
            embed.add_field(name=f"{start+i+1}. {res['title'][:60]}", 
                            value=f"👤 {res['uploader']} | 🕒 {dur}", inline=False)
        embed.set_footer(text=f"Halaman {self.page+1}/3")
        return embed

    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.gray)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
            await interaction.response.edit_message(embed=self.create_embed())

    @discord.ui.button(label="➡️", style=discord.ButtonStyle.gray)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page < 2:
            self.page += 1
            await interaction.response.edit_message(embed=self.create_embed())

    @discord.ui.button(label="Pilih Nomor", style=discord.ButtonStyle.green)
    async def select(self, interaction: discord.Interaction, button: discord.ui.Button):
        options = [discord.SelectOption(label=f"Lagu {i+1}", value=str(i)) for i in range(self.page*5, (self.page*5)+5)]
        sel = discord.ui.Select(placeholder="Pilih nomor lagu...", options=options)
        async def callback(inter):
            await inter.response.defer()
            await start_playing(inter, self.results[int(sel.values[0])]['url'])
        sel.callback = callback
        v = discord.ui.View(); v.add_item(sel)
        await interaction.response.send_message("Silahkan pilih:", view=v, ephemeral=True)

# --- UI: DASHBOARD UTAMA ---
class MusicDashboard(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.button(label="Pause", emoji="⏸️", style=discord.ButtonStyle.secondary)
    async def pp(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc.is_playing():
            vc.pause()
            button.label, button.emoji, button.style = "Resume", "▶️", discord.ButtonStyle.success
        else:
            vc.resume()
            button.label, button.emoji, button.style = "Pause", "⏸️", discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Volume", emoji="🔊", style=discord.ButtonStyle.gray)
    async def vol(self, interaction: discord.Interaction, button: discord.ui.Button):
        v = discord.ui.View()
        def make_btn(l, val):
            b = discord.ui.Button(label=l)
            async def c(i):
                interaction.guild.voice_client.source.volume = val
                await i.response.send_message(f"🔊 Volume set ke {int(val*100)}%", ephemeral=True)
            b.callback = c; return b
        v.add_item(make_btn("- Kecil", 0.2)); v.add_item(make_btn("+ Besar", 0.8))
        await interaction.response.send_message("Atur suara:", view=v, ephemeral=True)

    @discord.ui.button(label="Skip", emoji="⏭️", style=discord.ButtonStyle.primary)
    async def sk(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild.voice_client: interaction.guild.voice_client.stop()
        await interaction.response.send_message("⏭️ Skipped!", ephemeral=True)

    @discord.ui.button(label="Stop", emoji="🛑", style=discord.ButtonStyle.danger)
    async def st(self, interaction: discord.Interaction, button: discord.ui.Button):
        get_queue(self.guild_id).queue.clear()
        await interaction.guild.voice_client.disconnect()
        await interaction.response.edit_message(content="🛑 Stopped", embed=None, view=None)

# --- SETUP BOT ---
class ModernBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
    async def setup_hook(self):
        await self.tree.sync()
    async def on_ready(self):
        print(f"Logged in as {self.user}")

bot = ModernBot() # DISINI TADI ERORNYA, SEKARANG SUDAH ADA

# --- CORE LOGIC ---
async def start_playing(interaction, url):
    vc = interaction.guild.voice_client
    data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
    source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(data['url'], **FFMPEG_OPTIONS))
    q = get_queue(interaction.guild_id)
    track = {'source': source, 'title': data['title'], 'url': url, 'thumb': data.get('thumbnail')}

    if vc.is_playing() or vc.is_paused():
        q.queue.append(track)
        await interaction.followup.send(f"✅ Antrean: {track['title']}")
    else:
        q.current_track = track
        vc.play(source, after=lambda e: play_next(interaction))
        emb = discord.Embed(title="🎶 Sedang Memutar", description=f"[{track['title']}]({track['url']})", color=0x5865F2)
        emb.set_thumbnail(url=track['thumb'])
        await interaction.followup.send(embed=emb, view=MusicDashboard(interaction.guild_id))

def play_next(interaction):
    q = get_queue(interaction.guild_id)
    if q.queue:
        next_t = q.queue.popleft()
        q.current_track = next_t
        interaction.guild.voice_client.play(next_t['source'], after=lambda e: play_next(interaction))

# --- SLASH COMMANDS ---
@bot.tree.command(name="play", description="Cari musik dengan Dashboard")
async def play(interaction: discord.Interaction, pencarian: str):
    await interaction.response.defer()
    if not interaction.user.voice: return await interaction.followup.send("Masuk VC dulu!")
    if not interaction.guild.voice_client: await interaction.user.voice.channel.connect()

    if "http" in pencarian:
        await start_playing(interaction, pencarian)
    else:
        data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(f"ytsearch15:{pencarian}", download=False))
        v = SearchView(data['entries'])
        await interaction.followup.send(embed=v.create_embed(), view=v)

@bot.tree.command(name="keluar", description="Bot keluar dari voice")
async def keluar(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("👋 Keluar channel.")

@bot.tree.command(name="masuk", description="Bot masuk ke voice")
async def masuk(interaction: discord.Interaction):
    if interaction.user.voice:
        await interaction.user.voice.channel.connect()
        await interaction.response.send_message("📥 Sudah masuk!")
    else: await interaction.response.send_message("Masuk VC dulu!")

bot.run(TOKEN)

