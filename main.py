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

# ID Pembuat Bot (Untuk Link Profil Otomatis)
CREATOR_ID = 590774565115002880
CREATOR_NAME = "angelxxx6678"

# Setting Youtube-DL (Kualitas Terbaik & Stabil)
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
    'cookiefile': COOKIES_FILE, # Membaca cookies agar tidak kena blokir
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
}

# Setting FFmpeg (Agar lancar di Discord)
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

# --- KELAS PEMUTAR MUSIK ---
class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.duration = data.get('duration')
        self.thumbnail = data.get('thumbnail')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True):
        loop = loop or asyncio.get_event_loop()
        try:
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        except Exception as e:
            print(f"Error YTDL: {e}")
            return None

        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **FFMPEG_OPTIONS), data=data)

# --- STRUKTUR DATA ANTREAN ---
class MusicQueue:
    def __init__(self):
        self.queue = deque() # List lagu
        self.current_track = None
        self.voice_client = None
        self.ctx = None # Context interaksi terakhir

# Dictionary untuk menyimpan antrean per server (Guild)
queues = {}

def get_queue(guild_id):
    if guild_id not in queues:
        queues[guild_id] = MusicQueue()
    return queues[guild_id]

# --- SETUP BOT ---
class ModernMusicBot(commands.Bot):
    def __init__(self):
        # Setup Intents
        intents = discord.Intents.default()
        intents.message_content = True 
        super().__init__(command_prefix="!", intents=intents, help_command=None)

    async def setup_hook(self):
        # Sinkronisasi Slash Commands ke Discord
        print("🔄 Menyinkronkan Slash Commands...")
        await self.tree.sync()
        print("✅ Slash Commands Siap!")

    async def on_ready(self):
        print(f'🤖 {self.user} Online dan Siap Memutar Musik!')
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="/help | Music"))

bot = ModernMusicBot()

# --- FUNGSI PLAY NEXT (Otomatis putar lagu selanjutnya) ---
def play_next(guild_id, error=None):
    if error:
        print(f"Player error: {error}")
    
    q = get_queue(guild_id)
    
    if len(q.queue) > 0:
        # Ambil lagu berikutnya
        next_song = q.queue.popleft()
        q.current_track = next_song
        
        # Fungsi rekursif untuk lagu selanjutnya
        q.voice_client.play(next_song['source'], after=lambda e: play_next(guild_id, e))
        
        # Kirim notifikasi log
        print(f"Memutar: {next_song['title']}")
    else:
        q.current_track = None

# --- SLASH COMMANDS (MENU UTAMA) ---

@bot.tree.command(name="play", description="Memutar musik dari YouTube/SoundCloud")
@app_commands.describe(pencarian="Judul lagu atau Link URL")
async def play(interaction: discord.Interaction, pencarian: str):
    await interaction.response.defer() # Memberi waktu bot berpikir

    # Cek User ada di Voice Channel atau tidak
    if not interaction.user.voice:
        embed = discord.Embed(title="❌ Error", description="Masuk ke Voice Channel dulu ya!", color=discord.Color.red())
        return await interaction.followup.send(embed=embed)

    channel = interaction.user.voice.channel
    guild_id = interaction.guild_id
    q = get_queue(guild_id)

    # Bot Join Channel
    if not interaction.guild.voice_client:
        try:
            q.voice_client = await channel.connect()
        except Exception as e:
            return await interaction.followup.send(f"Gagal masuk channel: {e}")
    else:
        q.voice_client = interaction.guild.voice_client

    # Mencari Lagu
    player = await YTDLSource.from_url(pencarian, loop=bot.loop, stream=True)
    
    if player is None:
        return await interaction.followup.send("❌ Lagu tidak ditemukan atau dilindungi hak cipta.")

    # Simpan info lagu
    song_info = {
        'source': player,
        'title': player.title,
        'url': player.url,
        'thumbnail': player.thumbnail,
        'requester': interaction.user.mention
    }

    # Logika Play / Queue
    if q.voice_client.is_playing():
        # Jika sedang memutar, masukkan antrean
        q.queue.append(song_info)
        embed = discord.Embed(title="📝 Ditambahkan ke Antrean", description=f"[{player.title}]({player.url})", color=discord.Color.blue())
        embed.set_thumbnail(url=player.thumbnail)
        embed.set_footer(text=f"Posisi antrean: {len(q.queue)}")
        await interaction.followup.send(embed=embed)
    else:
        # Jika kosong, langsung putar
        q.current_track = song_info
        q.voice_client.play(player, after=lambda e: play_next(guild_id, e))
        
        embed = discord.Embed(title="🎶 Sedang Memutar", description=f"[{player.title}]({player.url})", color=discord.Color.green())
        embed.set_thumbnail(url=player.thumbnail)
        embed.add_field(name="Diminta oleh", value=interaction.user.mention)
        await interaction.followup.send(embed=embed)

@bot.tree.command(name="skip", description="Melewati lagu yang sedang diputar")
async def skip(interaction: discord.Interaction):
    if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
        interaction.guild.voice_client.stop()
        embed = discord.Embed(description="⏭️ **Skipped!** Lanjut ke lagu berikutnya.", color=discord.Color.orange())
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("Tidak ada lagu yang sedang diputar.", ephemeral=True)

@bot.tree.command(name="stop", description="Menghentikan musik dan membersihkan antrean")
async def stop(interaction: discord.Interaction):
    guild_id = interaction.guild_id
    q = get_queue(guild_id)
    
    q.queue.clear()
    if interaction.guild.voice_client:
        interaction.guild.voice_client.stop()
        await interaction.guild.voice_client.disconnect()
        embed = discord.Embed(description="⏹️ **Berhenti.** Terima kasih sudah mendengarkan!", color=discord.Color.red())
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("Saya tidak sedang berada di dalam channel.", ephemeral=True)

@bot.tree.command(name="volume", description="Mengatur volume (1-100)")
@app_commands.describe(level="Tingkat volume (persen)")
async def volume(interaction: discord.Interaction, level: int):
    if interaction.guild.voice_client and interaction.guild.voice_client.source:
        if 0 <= level <= 100:
            interaction.guild.voice_client.source.volume = level / 100
            embed = discord.Embed(description=f"🔊 Volume diatur ke **{level}%**", color=discord.Color.purple())
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("❌ Masukkan angka antara 0 sampai 100.", ephemeral=True)
    else:
        await interaction.response.send_message("Tidak ada lagu yang sedang diputar.", ephemeral=True)

@bot.tree.command(name="queue", description="Melihat daftar antrean lagu")
async def queue(interaction: discord.Interaction):
    q = get_queue(interaction.guild_id)
    if not q.queue and not q.current_track:
        return await interaction.response.send_message("📭 Antrean kosong.", ephemeral=True)

    desc = ""
    if q.current_track:
        desc += f"**Sedang Diputar:**\n🎵 {q.current_track['title']}\n\n"
    
    if q.queue:
        desc += "**Selanjutnya:**\n"
        for i, song in enumerate(q.queue):
            desc += f"{i+1}. {song['title']}\n"
    
    embed = discord.Embed(title="📜 Daftar Antrean", description=desc, color=discord.Color.gold())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="help", description="Menampilkan bantuan dan info pembuat bot")
async def help(interaction: discord.Interaction):
    # Membuat Embed yang Cantik
    embed = discord.Embed(
        title="🤖 Pusat Bantuan Musik",
        description="Gunakan perintah di bawah ini untuk mengontrol musik dengan mudah.",
        color=discord.Color.from_rgb(0, 255, 255) # Warna Cyan yang Elegan
    )
    
    # Daftar Perintah
    embed.add_field(name="🎵 `/play [judul/link]`", value="Memutar lagu dari YouTube/SoundCloud", inline=False)
    embed.add_field(name="⏭️ `/skip`", value="Melewati lagu saat ini", inline=True)
    embed.add_field(name="⏹️ `/stop`", value="Berhenti & Keluar channel", inline=True)
    embed.add_field(name="🔊 `/volume [1-100]`", value="Mengatur suara bot", inline=True)
    embed.add_field(name="📜 `/queue`", value="Melihat antrean lagu", inline=True)

    # Garis Pembatas
    embed.add_field(name="\u200b", value="━" * 20, inline=False)

    # --- BAGIAN TENTANG PEMBUAT (LINK PROFIL) ---
    # Menggunakan format <@ID> membuat nama menjadi link yang bisa diklik
    creator_mention = f"<@{CREATOR_ID}>"
    
    embed.add_field(
        name="✨ Tentang Bot",
        value=f"Bot musik canggih ini dikembangkan dan dikelola oleh:\n👤 **{creator_mention}** (`{CREATOR_NAME}`)\n\n*Klik nama di atas untuk melihat profil.*",
        inline=False
    )
    
    embed.set_footer(text="Music Bot v2.1 • High Quality Audio", icon_url=interaction.user.display_avatar.url)
    
    await interaction.response.send_message(embed=embed)

bot.run(TOKEN)
        
