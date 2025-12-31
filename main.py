import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import asyncio
import os
from collections import deque

# --- 1. KONFIGURASI GLOBAL ---
TOKEN = os.environ['DISCORD_TOKEN']
COOKIES_FILE = 'youtube_cookies.txt'

# Settingan YTDL untuk kualitas Audio Terbaik
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'default_search': 'ytsearch15',
    'quiet': True,
    'no_warnings': True,
    'nocheckcertificate': True,
    'cookiefile': COOKIES_FILE if os.path.exists(COOKIES_FILE) else None,
}

# FFmpeg dengan Normalisasi Suara & Bitrate Tinggi
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -nostdin',
    'options': '-vn -b:a 320k -af "loudnorm"'
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

# --- 2. SETUP BOT ---
class ModernBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.voice_states = True 
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print("🚀 SISTEM V14 (PREMIUM ALL-IN-ONE) ONLINE!")

bot = ModernBot()

# --- 3. QUEUE SYSTEM ---
queues = {}
class MusicQueue:
    def __init__(self):
        self.queue = deque()
        self.current_info = None
        self.loop = False
        self.volume = 1.0
        self.last_dashboard = None

def get_queue(guild_id):
    if guild_id not in queues: queues[guild_id] = MusicQueue()
    return queues[guild_id]

# --- 4. UI: VOLUME MIXER ---
class VolumeControlView(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=60)
        self.guild_id = guild_id

    def create_embed(self):
        q = get_queue(self.guild_id)
        vol_percent = int(q.volume * 100)
        embed = discord.Embed(title="🔊 Audio Control", color=0x3498db)
        bar = "🟦" * (vol_percent // 20) + "⬜" * (max(0, 5 - (vol_percent // 20)))
        embed.description = f"Volume Saat Ini: **{vol_percent}%**\n`{bar}`"
        return embed

    @discord.ui.button(label="-20%", style=discord.ButtonStyle.danger)
    async def down(self, interaction: discord.Interaction, button: discord.ui.Button):
        q = get_queue(self.guild_id)
        q.volume = max(0.0, q.volume - 0.2)
        if interaction.guild.voice_client and interaction.guild.voice_client.source:
            interaction.guild.voice_client.source.volume = q.volume
        await interaction.response.edit_message(embed=self.create_embed())

    @discord.ui.button(label="+20%", style=discord.ButtonStyle.success)
    async def up(self, interaction: discord.Interaction, button: discord.ui.Button):
        q = get_queue(self.guild_id)
        q.volume = min(2.0, q.volume + 0.2)
        if interaction.guild.voice_client and interaction.guild.voice_client.source:
            interaction.guild.voice_client.source.volume = q.volume
        await interaction.response.edit_message(embed=self.create_embed())

# --- 5. UI: DYNAMIC DASHBOARD (AESTHETIC) ---
class MusicDashboard(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.button(label="Pause/Resume", emoji="⏯️", style=discord.ButtonStyle.secondary)
    async def pp(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if not vc: return
        if vc.is_playing(): 
            vc.pause()
        else: 
            vc.resume()
        await interaction.response.defer()

    @discord.ui.button(label="Skip", emoji="⏭️", style=discord.ButtonStyle.primary)
    async def sk(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild.voice_client: 
            interaction.guild.voice_client.stop()
        await interaction.response.send_message("⏭️ Memutar lagu berikutnya...", ephemeral=True)

    @discord.ui.button(label="Loop", emoji="🔁", style=discord.ButtonStyle.gray)
    async def lp(self, interaction: discord.Interaction, button: discord.ui.Button):
        q = get_queue(self.guild_id)
        q.loop = not q.loop
        button.style = discord.ButtonStyle.success if q.loop else discord.ButtonStyle.gray
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Antrean", emoji="📜", style=discord.ButtonStyle.gray)
    async def list_q(self, interaction: discord.Interaction, button: discord.ui.Button):
        q = get_queue(self.guild_id)
        if not q.queue and not q.current_info:
            return await interaction.response.send_message("📪 Antrean kosong.", ephemeral=True)
        
        text = f"🎶 **Sedang Diputar:** {q.current_info['title'] if q.current_info else '-'}\n\n"
        if q.queue:
            text += "⌛ **Antrean Mendatang:**\n"
            for i, url in enumerate(list(q.queue)[:10]):
                text += f"**{i+1}.** {url}\n"
        else:
            text += "*(Tidak ada antrean)*"
        
        emb = discord.Embed(title="📜 Daftar Antrean Musik", description=text, color=0x2b2d31)
        await interaction.response.send_message(embed=emb, ephemeral=True)

    @discord.ui.button(label="Stop", emoji="⏹️", style=discord.ButtonStyle.danger)
    async def st(self, interaction: discord.Interaction, button: discord.ui.Button):
        q = get_queue(self.guild_id)
        q.queue.clear()
        if interaction.guild.voice_client: 
            interaction.guild.voice_client.stop()
            await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("⏹️ Musik dihentikan dan antrean dihapus.", ephemeral=True)

# --- 6. CORE LOGIC ---
async def start_stream(interaction, url):
    q = get_queue(interaction.guild_id)
    vc = interaction.guild.voice_client
    
    try:
        data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
        source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(data['url'], **FFMPEG_OPTIONS), volume=q.volume)
        q.current_info = {'title': data['title'], 'url': url, 'thumb': data.get('thumbnail'), 'dur': data.get('duration')}
        
        def after_playing(error):
            if error: print(f"FFmpeg Error: {error}")
            coro = next_logic(interaction)
            asyncio.run_coroutine_threadsafe(coro, bot.loop)

        vc.play(source, after=after_playing)
        
        if q.last_dashboard:
            try: await q.last_dashboard.delete()
            except: pass

        # --- AESTHETIC EMBED ---
        emb = discord.Embed(color=0x2f3136)
        emb.set_author(name="SEDANG DIPUTAR", icon_url="https://i.getpantry.cloud/apf/music_icon.gif")
        emb.title = f"✨ {data['title']}"
        emb.url = url
        emb.set_thumbnail(url=data.get('thumbnail'))
        
        dur_str = f"{data.get('duration')//60:02d}:{data.get('duration')%60:02d}"
        emb.add_field(name="👤 Pengirim", value=f"{interaction.user.mention}", inline=True)
        emb.add_field(name="⏱️ Durasi", value=f"`{dur_str}`", inline=True)
        emb.add_field(name="🎧 Kualitas", value="`HQ 320kbps`", inline=True)
        emb.add_field(name="Progress", value="`🔘" + "▬▬▬▬▬▬▬▬▬▬" + "`", inline=False)
        
        q.last_dashboard = await interaction.channel.send(embed=emb, view=MusicDashboard(interaction.guild_id))
    except Exception as e:
        await interaction.channel.send(f"❌ Error Audio: {e}")

async def next_logic(interaction):
    q = get_queue(interaction.guild_id)
    vc = interaction.guild.voice_client
    if not vc or not vc.is_connected(): return

    # JEDA KRUSIAL AGAR SKIP SELALU DARI 00:00
    await asyncio.sleep(1.5) 
    
    if q.loop and q.current_info:
        await start_stream(interaction, q.current_info['url'])
    elif q.queue:
        await start_stream(interaction, q.queue.popleft())
    else:
        q.current_info = None
        if q.last_dashboard:
            try: await q.last_dashboard.delete()
            except: pass
        await interaction.channel.send("✅ Antrean selesai. Bot standby.", delete_after=10)

async def play_music(interaction, url):
    q = get_queue(interaction.guild_id)
    if not interaction.guild.voice_client:
        if interaction.user.voice:
            await interaction.user.voice.channel.connect()
        else:
            return await interaction.followup.send("❌ Masuk Voice Channel dulu!", ephemeral=True)
    
    vc = interaction.guild.voice_client
    if vc.is_playing() or vc.is_paused():
        q.queue.append(url)
        data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
        emb = discord.Embed(description=f"✅ **Ditambahkan ke antrean:** [{data['title']}]({url})", color=0x2ecc71)
        return await interaction.followup.send(embed=emb, ephemeral=True)
    
    await start_stream(interaction, url)

# --- 7. SLASH COMMANDS ---

@bot.tree.command(name="play", description="Putar musik favoritmu")
async def play(interaction: discord.Interaction, cari: str):
    await interaction.response.defer()
    if not interaction.user.voice: return await interaction.followup.send("❌ Masuk VC dulu!", ephemeral=True)
    
    if "http" in cari:
        await play_music(interaction, cari)
        await interaction.followup.send("✅ Memproses link...", ephemeral=True)
    else:
        # Search logic (Ambil hasil pertama)
        data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(f"ytsearch1:{cari}", download=False))
        if not data['entries']: return await interaction.followup.send("❌ Tidak ditemukan.")
        await play_music(interaction, data['entries'][0]['webpage_url'])
        await interaction.followup.send(f"🔍 Menemukan: **{data['entries'][0]['title']}**", ephemeral=True)

@bot.tree.command(name="masuk", description="Panggil bot ke Voice Channel")
async def masuk(interaction: discord.Interaction):
    if interaction.user.voice:
        channel = interaction.user.voice.channel
        await channel.connect()
        await interaction.response.send_message(f"👋 Halo! Aku sudah di **{channel.name}**")
    else:
        await interaction.response.send_message("❌ Kamu harus di VC dulu!", ephemeral=True)

@bot.tree.command(name="keluar", description="Keluarkan bot dari Voice Channel")
async def keluar(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        q = get_queue(interaction.guild_id)
        q.queue.clear()
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("👋 Sampai jumpa lagi!")
    else:
        await interaction.response.send_message("❌ Aku sedang tidak di VC.", ephemeral=True)

@bot.tree.command(name="skip", description="Lewati lagu saat ini")
async def skip_cmd(interaction: discord.Interaction):
    if interaction.guild.voice_client and interaction.guild.voice_client.is_playing(): 
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("⏭️ Lagu dilewati!")
    else:
        await interaction.response.send_message("❌ Tidak ada lagu yang diputar.", ephemeral=True)

@bot.tree.command(name="volume", description="Atur volume (0-200)")
async def volume(interaction: discord.Interaction, persen: int):
    q = get_queue(interaction.guild_id)
    if 0 <= persen <= 200:
        q.volume = persen / 100
        if interaction.guild.voice_client and interaction.guild.voice_client.source:
            interaction.guild.voice_client.source.volume = q.volume
        await interaction.response.send_message(f"🔊 Volume diatur ke **{persen}%**")
    else:
        await interaction.response.send_message("❌ Masukkan angka 0-200.", ephemeral=True)

@bot.tree.command(name="queue", description="Lihat daftar antrean")
async def queue_list(interaction: discord.Interaction):
    q = get_queue(interaction.guild_id)
    if not q.queue: return await interaction.response.send_message("📪 Antrean kosong.")
    
    emb = discord.Embed(title="📜 Antrean Musik", color=0x9b59b6)
    text = ""
    for i, url in enumerate(list(q.queue)[:15]):
        text += f"**{i+1}.** {url}\n"
    emb.description = text
    await interaction.response.send_message(embed=emb)

@bot.tree.command(name="help", description="Panduan bot")
async def help_cmd(interaction: discord.Interaction):
    emb = discord.Embed(title="🤖 Panduan Musik Bot Premium", color=0x3498db)
    emb.description = "Bot musik dengan kualitas audio 320kbps & High Stability."
    emb.add_field(name="🎵 Kontrol", value="`/play`, `/skip`, `/volume`, `/queue`", inline=False)
    emb.add_field(name="⚙️ VC", value="`/masuk`, `/keluar`", inline=False)
    emb.set_footer(text="Dibuat dengan ❤️ • ikiii Project")
    await interaction.response.send_message(embed=emb)

# --- 8. AUTO DISCONNECT JIKA SEPI ---
@bot.event
async def on_voice_state_update(member, before, after):
    if member.id == bot.user.id: return
    if before.channel is not None:
        vc = member.guild.voice_client
        if vc and vc.channel.id == before.channel.id and len(before.channel.members) == 1:
            await asyncio.sleep(60) 
            if len(before.channel.members) == 1:
                await vc.disconnect()

bot.run(TOKEN)
