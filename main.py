import discord
from discord.ext import commands
import yt_dlp
import asyncio
import os

TOKEN = os.environ['DISCORD_TOKEN']

# Konfigurasi Audio yang paling stabil untuk Replit
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'nocheckcertificate': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
    'cookiefile': 'youtube_cookies.txt',
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        if 'entries' in data:
            data = data['entries'][0]
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **FFMPEG_OPTIONS), data=data)

class MusicBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        super().__init__(command_prefix='!', intents=intents)

    async def on_ready(self):
        print(f'✅ Bot siap di akun: {self.user}')

bot = MusicBot()

@bot.command()
async def play(ctx, *, search: str):
    if not ctx.author.voice:
        return await ctx.send("❌ Masuk ke voice channel dulu!")

    # Jika bot belum join, coba connect dengan timeout lebih lama
    if not ctx.voice_client:
        try:
            await ctx.author.voice.channel.connect(timeout=60.0, reconnect=True)
        except Exception as e:
            return await ctx.send(f"❌ Gagal koneksi suara: {e}")

    #async with ctx.typing():
        try:
            player = await YTDLSource.from_url(search, loop=bot.loop, stream=True)
            if ctx.voice_client.is_playing():
                ctx.voice_client.stop()
            
            ctx.voice_client.play(player)
            
            embed = discord.Embed(title="🎶 Sedang Diputar", description=player.title, color=discord.Color.green())
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"❌ Terjadi kesalahan saat memutar: {e}")

bot.run(TOKEN)

