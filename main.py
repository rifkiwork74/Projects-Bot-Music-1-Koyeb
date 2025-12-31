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

YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'default_search': 'ytsearch15',
    'quiet': True,
    'no_warnings': True,
    'nocheckcertificate': True,
    'cookiefile': COOKIES_FILE if os.path.exists(COOKIES_FILE) else None,
}

FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}
ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

# --- 2. SETUP BOT ---
class ModernBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Sync paksa agar semua perintah muncul di Discord
        await self.tree.sync()
        print("✅ Semua Fitur (Play, Stop, Help, Loop, Volume) Berhasil Disinkronkan!")

bot = ModernBot()

# --- 3. QUEUE SYSTEM ---
queues = {}
class MusicQueue:
    def __init__(self):
        self.queue = deque()
        self.current_info = None
        self.loop = False
        self.last_dashboard = None

def get_queue(guild_id):
    if guild_id not in queues: queues[guild_id] = MusicQueue()
    return queues[guild_id]

# --- 4. UI: SEARCH PAGINATION (3 HALAMAN) ---
class SearchView(discord.ui.View):
    def __init__(self, results, interaction_user):
        super().__init__(timeout=60)
        self.results = results
        self.user = interaction_user
        self.page = 0

    def create_embed(self):
        start = self.page * 5
        current_list = self.results[start:start+5]
        embed = discord.Embed(title="🔍 Hasil Pencarian Musik", color=0x2b2d31)
        for i, res in enumerate(current_list):
            dur = f"{res.get('duration')//60}:{res.get('duration')%60:02d}"
            embed.add_field(
                name=f"{start+i+1}. {res['title'][:60]}", 
                value=f"🕒 Durasi: {dur} | 👤 {res['uploader']}", 
                inline=False
            )
        embed.set_footer(text=f"Halaman {self.page+1}/3 • Pilih nomor lagu di menu bawah")
        return embed

    @discord.ui.button(label="⬅️ Back", style=discord.ButtonStyle.gray)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
            await interaction.response.edit_message(embed=self.create_embed())

    @discord.ui.button(label="Next ➡️", style=discord.ButtonStyle.gray)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page < 2:
            self.page += 1
            await interaction.response.edit_message(embed=self.create_embed())

    @discord.ui.button(label="Konfirmasi Pilihan", style=discord.ButtonStyle.green)
    async def select(self, interaction: discord.Interaction, button: discord.ui.Button):
        options = [discord.SelectOption(label=f"Lagu Nomor {i+1}", value=str(i)) for i in range(self.page*5, (self.page*5)+5)]
        sel = discord.ui.Select(placeholder="Klik di sini untuk memilih nomor lagu...", options=options)
        
        async def callback(inter: discord.Interaction):
            await inter.response.defer()
            # PENTING: Jalankan play_music dari sini
            await play_music(inter, self.results[int(sel.values[0])]['url'])
        
        sel.callback = callback
        new_view = discord.ui.View(); new_view.add_item(sel)
        await interaction.response.send_message("Silahkan pilih lagu kamu:", view=new_view, ephemeral=True)

# --- 5. UI: DYNAMIC DASHBOARD ---
class MusicDashboard(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.button(label="Pause/Resume", emoji="⏯️", style=discord.ButtonStyle.secondary)
    async def pp(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc:
            if vc.is_playing(): vc.pause()
            else: vc.resume()
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Loop", emoji="🔁", style=discord.ButtonStyle.gray)
    async def lp(self, interaction: discord.Interaction, button: discord.ui.Button):
        q = get_queue(self.guild_id)
        q.loop = not q.loop
        button.style = discord.ButtonStyle.success if q.loop else discord.ButtonStyle.gray
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(f"🔁 Mode Loop: {'AKTIF' if q.loop else 'NONAKTIF'}", ephemeral=True)

    @discord.ui.button(label="Skip", emoji="⏭️", style=discord.ButtonStyle.primary)
    async def sk(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild.voice_client:
            interaction.guild.voice_client.stop()
            await interaction.response.send_message("⏭️ Lagu diskip!", ephemeral=True)

    @discord.ui.button(label="Stop", emoji="🛑", style=discord.ButtonStyle.danger)
    async def st(self, interaction: discord.Interaction, button: discord.ui.Button):
        q = get_queue(self.guild_id)
        q.queue.clear()
        if interaction.guild.voice_client: await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("🛑 Musik Berhenti & Antrean Dihapus.", ephemeral=True)

# --- 6. LOGIKA INTI ---
async def play_music(interaction, url):
    q = get_queue(interaction.guild_id)
    
    # FIX: Pastikan bot masuk VC TERLEBIH DAHULU sebelum cek is_playing
    if not interaction.guild.voice_client:
        if interaction.user.voice:
            await interaction.user.voice.channel.connect()
        else:
            return await interaction.channel.send("❌ Kamu harus berada di Voice Channel!")

    vc = interaction.guild.voice_client
    if vc.is_playing() or vc.is_paused():
        q.queue.append(url)
        # Ambil judul sebentar untuk notifikasi
        data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
        return await interaction.followup.send(f"✅ Antrean: **{data['title']}**", ephemeral=True)
    
    await start_stream(interaction, url)

async def start_stream(interaction, url):
    q = get_queue(interaction.guild_id)
    vc = interaction.guild.voice_client
    
    try:
        data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
        source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(data['url'], **FFMPEG_OPTIONS))
        q.current_info = {'title': data['title'], 'url': url, 'thumb': data.get('thumbnail')}
        
        vc.play(source, after=lambda e: bot.loop.create_task(next_logic(interaction)))
        
        # Bersihkan dashboard lama
        if q.last_dashboard:
            try: await q.last_dashboard.delete()
            except: pass

        emb = discord.Embed(title="🎶 Sedang Memutar", description=f"**[{data['title']}]({url})**", color=0x5865F2)
        emb.set_thumbnail(url=data.get('thumbnail'))
        emb.set_footer(text=f"Requested by: {interaction.user.name}")
        
        q.last_dashboard = await interaction.channel.send(embed=emb, view=MusicDashboard(interaction.guild_id))
    except Exception as e:
        await interaction.channel.send(f"❌ Terjadi kesalahan YouTube: {e}")

async def next_logic(interaction):
    q = get_queue(interaction.guild_id)
    vc = interaction.guild.voice_client
    if not vc: return
    
    if q.loop and q.current_info:
        await start_stream(interaction, q.current_info['url'])
    elif q.queue:
        await start_stream(interaction, q.queue.popleft())
    else:
        q.current_info = None

# --- 7. SLASH COMMANDS ---
@bot.tree.command(name="play", description="Putar musik dari link atau cari judul (3 Halaman)")
async def play(interaction: discord.Interaction, search: str):
    await interaction.response.defer()
    if not interaction.user.voice: return await interaction.followup.send("❌ Masuk VC dulu!", ephemeral=True)

    if "http" in search:
        # Jika link, langsung putar
        await play_music(interaction, search)
        await interaction.followup.send("🔗 Memproses Link...", ephemeral=True)
    else:
        # Jika teks, cari 15 hasil
        data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(f"ytsearch15:{search}", download=False))
        view = SearchView(data['entries'], interaction.user)
        await interaction.followup.send(embed=view.create_embed(), view=view)

@bot.tree.command(name="help", description="Informasi Panduan & Pengembang")
async def help_cmd(interaction: discord.Interaction):
    emb_guide = discord.Embed(title="📖 Panduan Media Player", color=0x3498db)
    emb_guide.description = "• **/play** : Putar musik (Link/Teks)\n• **/stop** : Berhenti & Keluar\n• **/help** : Info bot"
    
    emb_dev = discord.Embed(title="👨‍💻 Developer Info", color=0x9b59b6)
    emb_dev.description = "Dibuat oleh **ikiiii 😅** (Username: `angelxxx6678`)\nID: `590774565115002880`"
    
    await interaction.response.send_message(embeds=[emb_guide, emb_dev])

@bot.tree.command(name="stop", description="Berhenti memutar musik")
async def stop(interaction: discord.Interaction):
    q = get_queue(interaction.guild_id)
    q.queue.clear()
    if interaction.guild.voice_client: await interaction.guild.voice_client.disconnect()
    await interaction.response.send_message("🛑 Musik telah berhenti.", ephemeral=True)

bot.run(TOKEN)
