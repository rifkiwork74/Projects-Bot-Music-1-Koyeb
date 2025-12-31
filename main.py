import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import asyncio
import os
from collections import deque

# --- KONFIGURASI ---
TOKEN = os.environ['DISCORD_TOKEN']
COOKIES_FILE = 'youtube_cookies.txt'

YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
    'cookiefile': COOKIES_FILE,
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

# --- INTERFACE TOMBOL MODERN ---
class MusicControlView(discord.ui.View):
    def __init__(self, bot, guild_id):
        super().__init__(timeout=None) # Tombol tidak akan mati
        self.bot = bot
        self.guild_id = guild_id

    @discord.ui.button(label="⏯️ Pause/Resume", style=discord.ButtonStyle.secondary)
    async def play_pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if not vc: return
        
        if vc.is_playing():
            vc.pause()
            await interaction.response.send_message("⏸️ Musik di-pause", ephemeral=True)
        elif vc.is_paused():
            vc.resume()
            await interaction.response.send_message("▶️ Musik dilanjutkan", ephemeral=True)

    @discord.ui.button(label="⏭️ Skip", style=discord.ButtonStyle.primary)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
            await interaction.response.send_message("⏭️ Lagu dilewati", ephemeral=True)

    @discord.ui.button(label="🔊", style=discord.ButtonStyle.gray)
    async def vol_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc and vc.source:
            new_vol = min(vc.source.volume + 0.1, 1.0)
            vc.source.volume = new_vol
            await interaction.response.send_message(f"🔊 Volume: {int(new_vol*100)}%", ephemeral=True)

    @discord.ui.button(label="⏹️ Stop", style=discord.ButtonStyle.danger)
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        q = get_queue(self.guild_id)
        q.queue.clear()
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.disconnect()
            await interaction.response.send_message("⏹️ Bot berhenti dan keluar.", ephemeral=True)

# --- LOGIKA CORE (YTDL & QUEUE) ---
class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.thumbnail = data.get('thumbnail')
        self.url = data.get('webpage_url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        if 'entries' in data: data = data['entries'][0]
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **FFMPEG_OPTIONS), data=data)

class MusicQueue:
    def __init__(self):
        self.queue = deque()
        self.current_track = None

queues = {}
def get_queue(guild_id):
    if guild_id not in queues: queues[guild_id] = MusicQueue()
    return queues[guild_id]

# --- BOT SETUP ---
class ModernBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()

bot = ModernBot()

def play_next(interaction, guild_id):
    q = get_queue(guild_id)
    if len(q.queue) > 0:
        next_song = q.queue.popleft()
        q.current_track = next_song
        
        # Buat view tombol baru untuk lagu berikutnya
        view = MusicControlView(bot, guild_id)
        
        embed = discord.Embed(title="🎶 Sedang Memutar", description=f"[{next_song['title']}]({next_song['url']})", color=0x2ecc71)
        embed.set_thumbnail(url=next_song['thumbnail'])
        
        # Kirim pesan baru dengan tombol
        asyncio.run_coroutine_threadsafe(interaction.channel.send(embed=embed, view=view), bot.loop)
        
        interaction.guild.voice_client.play(next_song['source'], after=lambda e: play_next(interaction, guild_id))

@bot.tree.command(name="play", description="Putar musik dengan interface modern")
async def play(interaction: discord.Interaction, search: str):
    await interaction.response.defer()
    
    if not interaction.user.voice:
        return await interaction.followup.send("❌ Masuk ke Voice Channel dulu!")

    vc = interaction.guild.voice_client
    if not vc:
        vc = await interaction.user.voice.channel.connect()

    player = await YTDLSource.from_url(search, loop=bot.loop, stream=True)
    q = get_queue(interaction.guild_id)

    song_info = {
        'source': player, 'title': player.title, 
        'thumbnail': player.thumbnail, 'url': player.url
    }

    if vc.is_playing() or vc.is_paused():
        q.queue.append(song_info)
        await interaction.followup.send(f"📝 **{player.title}** ditambahkan ke antrean.")
    else:
        q.current_track = song_info
        view = MusicControlView(bot, interaction.guild_id)
        
        embed = discord.Embed(title="🎶 Sedang Memutar", description=f"[{player.title}]({player.url})", color=0x2ecc71)
        embed.set_thumbnail(url=player.thumbnail)
        embed.set_footer(text=f"Request oleh: {interaction.user.display_name}")
        
        await interaction.followup.send(embed=embed, view=view)
        vc.play(player, after=lambda e: play_next(interaction, interaction.guild_id))

bot.run(TOKEN)
        
