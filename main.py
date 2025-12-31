
import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import asyncio
import os
from collections import deque

# --- KONFIGURASI ---
TOKEN = os.environ['DISCORD_TOKEN']
COOKIES_FILE = 'youtube_cookies.txt' # PASTIKAN FILE INI SUDAH DI-UPLOAD

YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'default_search': 'ytsearch15',
    'quiet': True,
    'no_warnings': True,
    'cookiefile': COOKIES_FILE if os.path.exists(COOKIES_FILE) else None,
}

FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}
ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

# --- DATA STORAGE ---
queues = {}
class MusicQueue:
    def __init__(self):
        self.queue = deque()
        self.current_track = None

def get_queue(guild_id):
    if guild_id not in queues: queues[guild_id] = MusicQueue()
    return queues[guild_id]

# --- UI: DASHBOARD ---
class MusicDashboard(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.button(label="Pause", emoji="⏸️", style=discord.ButtonStyle.secondary)
    async def pp(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if not vc: return
        if vc.is_playing():
            vc.pause()
            button.label, button.emoji, button.style = "Resume", "▶️", discord.ButtonStyle.success
        else:
            vc.resume()
            button.label, button.emoji, button.style = "Pause", "⏸️", discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Vol -", style=discord.ButtonStyle.gray)
    async def vol_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc.source:
            vc.source.volume = max(vc.source.volume - 0.2, 0.1)
            await interaction.response.send_message(f"🔉 Volume: {int(vc.source.volume*100)}%", ephemeral=True)

    @discord.ui.button(label="Vol +", style=discord.ButtonStyle.gray)
    async def vol_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc.source:
            vc.source.volume = min(vc.source.volume + 0.2, 1.0)
            await interaction.response.send_message(f"🔊 Volume: {int(vc.source.volume*100)}%", ephemeral=True)

    @discord.ui.button(label="Skip", emoji="⏭️", style=discord.ButtonStyle.primary)
    async def sk(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild.voice_client:
            interaction.guild.voice_client.stop()
            await interaction.response.send_message("⏭️ Skipped!", ephemeral=True)

    @discord.ui.button(label="Stop", emoji="🛑", style=discord.ButtonStyle.danger)
    async def st(self, interaction: discord.Interaction, button: discord.ui.Button):
        get_queue(self.guild_id).queue.clear()
        if interaction.guild.voice_client: await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("🛑 Bot berhenti.", ephemeral=True)

# --- SETUP BOT ---
class ModernBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
    async def setup_hook(self):
        await self.tree.sync()

bot = ModernBot()

# --- CORE LOGIC ---
async def start_playing(interaction, url):
    q = get_queue(interaction.guild_id)
    vc = interaction.guild.voice_client
    
    try:
        data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
    except Exception as e:
        return await interaction.followup.send(f"❌ Eror YouTube: Masukkan file `youtube_cookies.txt` ke bot!")

    source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(data['url'], **FFMPEG_OPTIONS))
    track = {'source': source, 'title': data['title'], 'url': url, 'thumb': data.get('thumbnail')}

    if vc.is_playing() or vc.is_paused():
        q.queue.append(track)
        await interaction.followup.send(f"✅ Masuk antrean: **{track['title']}**")
    else:
        q.current_track = track
        vc.play(source, after=lambda e: bot.loop.create_task(play_next(interaction)))
        emb = discord.Embed(title="🎶 Sedang Memutar", description=f"[{track['title']}]({track['url']})", color=0x5865F2)
        emb.set_thumbnail(url=track['thumb'])
        await interaction.followup.send(embed=emb, view=MusicDashboard(interaction.guild_id))

async def play_next(interaction):
    q = get_queue(interaction.guild_id)
    vc = interaction.guild.voice_client
    if not vc or not q.queue: return

    next_track = q.queue.popleft()
    q.current_track = next_track
    
    # Re-extract URL untuk menghindari expire link
    data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(next_track['url'], download=False))
    new_source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(data['url'], **FFMPEG_OPTIONS))
    
    vc.play(new_source, after=lambda e: bot.loop.create_task(play_next(interaction)))
    
    emb = discord.Embed(title="🎶 Lanjut Memutar", description=f"[{next_track['title']}]({next_track['url']})", color=0x5865F2)
    emb.set_thumbnail(url=next_track['thumb'])
    await interaction.channel.send(embed=emb, view=MusicDashboard(interaction.guild_id))

@bot.tree.command(name="play", description="Mainkan musik")
async def play(interaction: discord.Interaction, pencarian: str):
    await interaction.response.defer()
    if not interaction.user.voice: return await interaction.followup.send("Masuk VC dulu!")
    if not interaction.guild.voice_client: await interaction.user.voice.channel.connect()
    
    await start_playing(interaction, pencarian)

bot.run(TOKEN)
            
