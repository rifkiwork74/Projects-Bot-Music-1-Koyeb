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

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -nostdin',
    'options': '-vn -b:a 320k -af "loudnorm" -threads 2'
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
        print("✅ SISTEM V16 FINAL ONLINE!")

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

# --- 4. AUTO-DISCONNECT 15 DETIK DENGAN RESPON ---
@bot.event
async def on_voice_state_update(member, before, after):
    if not member.bot and before.channel is not None:
        vc = member.guild.voice_client
        if vc and len(before.channel.members) == 1:
            msg_chan = vc.guild.system_channel or vc.channel
            if msg_chan:
                await msg_chan.send("⚠️ **Informasi:** Tidak ada pengguna di Voice Channel. Bot akan otomatis keluar dalam **15 detik**.", delete_after=15)
            
            await asyncio.sleep(15)
            if vc and vc.channel and len(vc.channel.members) == 1:
                q = get_queue(member.guild.id)
                q.queue.clear()
                await vc.disconnect()

# --- 5. UI: PEMILIH LAGU (NAVIGASI + AUTO-DELETE + FULL 10 OPTIONS) ---
class SearchControlView(discord.ui.View):
    def __init__(self, entries, user, page=0):
        super().__init__(timeout=60)
        self.entries = entries
        self.user = user
        self.page = page
        self.start_idx = page * 3
        self.end_idx = self.start_idx + 3
        self.current_slice = entries[self.start_idx:self.end_idx]

    @discord.ui.button(label="⬅️ Back", style=discord.ButtonStyle.gray)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user: return
        if self.page > 0:
            await interaction.response.edit_message(view=SearchControlView(self.entries, self.user, self.page - 1))

    @discord.ui.button(label="Next ➡️", style=discord.ButtonStyle.gray)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user: return
        if (self.page + 1) * 3 < len(self.entries):
            await interaction.response.edit_message(view=SearchControlView(self.entries, self.user, self.page + 1))

    @discord.ui.button(label="🎯 Pilih Lagu", style=discord.ButtonStyle.primary)
    async def pick(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user: return
        
        # Menampilkan semua 10 lagu dari hasil pencarian (bukan cuma yang di halaman itu)
        options = [discord.SelectOption(label=f"Lagu Nomor {i + 1}", value=entry['webpage_url'], description=entry['title'][:50]) for i, entry in enumerate(self.entries)]
        select = discord.ui.Select(placeholder="Pilih nomor lagu (1-10)...", options=options)
        
        async def select_callback(inter: discord.Interaction):
            await inter.response.defer()
            await play_music(inter, select.values[0])
            try: await interaction.delete_original_response() # Pesan pencarian otomatis hilang
            except: pass

        select.callback = select_callback
        new_view = discord.ui.View(timeout=30); new_view.add_item(select)
        await interaction.response.edit_message(content="✅ Silakan pilih nomor lagu di bawah ini:", view=new_view)

# --- 6. UI: DASHBOARD & VOLUME ---
class VolumeControlView(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=60); self.guild_id = guild_id
    def create_embed(self):
        q = get_queue(self.guild_id); vol_percent = int(q.volume * 100)
        embed = discord.Embed(title="🎚️ Pengaturan Audio", color=0x3498db)
        bar = "▰" * (vol_percent // 20) + "▱" * (max(0, 5 - (vol_percent // 20)))
        embed.description = f"Volume Saat Ini: **{vol_percent}%**\n`{bar}`"; return embed
    @discord.ui.button(label="-20%", style=discord.ButtonStyle.danger, emoji="🔉")
    async def down(self, interaction: discord.Interaction, button: discord.ui.Button):
        q = get_queue(self.guild_id); q.volume = max(0.0, q.volume - 0.2)
        if interaction.guild.voice_client and interaction.guild.voice_client.source: interaction.guild.voice_client.source.volume = q.volume
        await interaction.response.edit_message(embed=self.create_embed())
    @discord.ui.button(label="+20%", style=discord.ButtonStyle.success, emoji="🔊")
    async def up(self, interaction: discord.Interaction, button: discord.ui.Button):
        q = get_queue(self.guild_id); q.volume = min(2.0, q.volume + 0.2)
        if interaction.guild.voice_client and interaction.guild.voice_client.source: interaction.guild.voice_client.source.volume = q.volume
        await interaction.response.edit_message(embed=self.create_embed())

class MusicDashboard(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=None); self.guild_id = guild_id
    @discord.ui.button(label="Jeda", emoji="⏸️", style=discord.ButtonStyle.secondary)
    async def pp(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if not vc: return
        if vc.is_playing(): vc.pause(); button.emoji = "▶️"; button.label = "Lanjut"; button.style = discord.ButtonStyle.success 
        else: vc.resume(); button.emoji = "⏸️"; button.label = "Jeda"; button.style = discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=self)
    @discord.ui.button(label="Volume", emoji="🔊", style=discord.ButtonStyle.gray)
    async def vol(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = VolumeControlView(self.guild_id); await interaction.response.send_message(embed=view.create_embed(), view=view, ephemeral=True)
    
    # FITUR SMART QUEUE (TETAP)
    @discord.ui.button(label="Antrean", emoji="📜", style=discord.ButtonStyle.gray)
    async def list_q(self, interaction: discord.Interaction, button: discord.ui.Button):
        q = get_queue(self.guild_id)
        if not q.queue: return await interaction.response.send_message("📪 Antrean kosong.", ephemeral=True, delete_after=20)
        emb = discord.Embed(title="📜 Antrean Musik Saat Ini", color=0x2b2d31)
        description = ""
        options = []
        for i, item in enumerate(list(q.queue)[:10]):
            description += f"**{i+1}.** {item['title'][:50]}...\n"
            options.append(discord.SelectOption(label=f"{i+1}. {item['title'][:25]}", value=str(i)))
        emb.description = description
        select = discord.ui.Select(placeholder="🎯 Pilih lagu untuk dilompati...", options=options)
        async def select_callback(inter: discord.Interaction):
            idx = int(select.values[0]); chosen = q.queue[idx]; del q.queue[idx]; q.queue.appendleft(chosen)
            if inter.guild.voice_client: inter.guild.voice_client.stop()
            await inter.response.send_message(f"🚀 Memutar: **{chosen['title']}**", ephemeral=True, delete_after=5)
        select.callback = select_callback
        view = discord.ui.View(); view.add_item(select)
        await interaction.response.send_message(embed=emb, view=view, ephemeral=True)

    @discord.ui.button(label="Skip", emoji="⏭️", style=discord.ButtonStyle.primary)
    async def sk(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild.voice_client: interaction.guild.voice_client.stop()
        await interaction.response.send_message("⏭️ Lagu dilewati!", ephemeral=True, delete_after=5)
    @discord.ui.button(label="Stop", emoji="⏹️", style=discord.ButtonStyle.danger)
    async def st(self, interaction: discord.Interaction, button: discord.ui.Button):
        q = get_queue(self.guild_id); q.queue.clear()
        if interaction.guild.voice_client: await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("⏹️ Player dimatikan.", ephemeral=True, delete_after=5)

# --- 7. CORE LOGIC ---
async def start_stream(interaction, url):
    q = get_queue(interaction.guild_id); vc = interaction.guild.voice_client
    if not vc: return
    try:
        data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
        source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(data['url'], **FFMPEG_OPTIONS), volume=q.volume)
        def after_playing(error): asyncio.run_coroutine_threadsafe(next_logic(interaction), bot.loop)
        vc.play(source, after=after_playing)
        if q.last_dashboard:
            try: await q.last_dashboard.delete()
            except: pass
        emb = discord.Embed(title=f"🎶 Sedang Diputar", description=f"**[{data['title']}]({url})**", color=0x2ecc71); emb.set_thumbnail(url=data.get('thumbnail'))
        q.last_dashboard = await interaction.channel.send(embed=emb, view=MusicDashboard(interaction.guild_id))
    except Exception as e: await interaction.channel.send(f"❌ Error Audio: {e}")

async def next_logic(interaction):
    q = get_queue(interaction.guild_id)
    if q.queue: next_song = q.queue.popleft(); await start_stream(interaction, next_song['url'])
    else:
        if q.last_dashboard:
            try: await q.last_dashboard.delete()
            except: pass
        await interaction.channel.send("✅ Antrean selesai.", delete_after=10)

async def play_music(interaction, url):
    q = get_queue(interaction.guild_id)
    
    # Memastikan bot terhubung ke Voice Channel
    if not interaction.guild.voice_client:
        await interaction.user.voice.channel.connect()
    
    vc = interaction.guild.voice_client
    
    if vc.is_playing() or vc.is_paused():
        # JIKA LAGU MASUK ANTREAN
        data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
        q.queue.append({'title': data['title'], 'url': url})
        emb = discord.Embed(description=f"✅ **Berhasil Masuk Antrean:**\n{data['title']}", color=0x3498db)
        
        # MEMBERIKAN RESPONS AGAR LOADING HILANG
        if interaction.response.is_done():
            await interaction.followup.send(embed=emb, ephemeral=True, delete_after=20)
        else:
            await interaction.response.send_message(embed=emb, ephemeral=True, delete_after=20)
    else:
        # JIKA LAGU LANGSUNG DIPUTAR
        # Kirim respons singkat dulu agar "is thinking" hilang
        if not interaction.response.is_done():
            await interaction.response.send_message("🎶 **Memulai pemutaran...**", ephemeral=True, delete_after=2)
        else:
            await interaction.followup.send("🎶 **Memulai pemutaran...**", ephemeral=True, delete_after=2)
            
        await start_stream(interaction, url)

async def start_stream(interaction, url):
    q = get_queue(interaction.guild_id)
    vc = interaction.guild.voice_client
    if not vc: return
    
    try:
        # Stop jika ada proses menggantung
        if vc.is_playing() or vc.is_paused():
            vc.stop()
            await asyncio.sleep(0.5)

        data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
        
        # Reset FFmpeg Options untuk memastikan mulai dari 00:00
        source = discord.PCMVolumeTransformer(
            discord.FFmpegPCMAudio(data['url'], **FFMPEG_OPTIONS), 
            volume=q.volume
        )
        
        def after_playing(error):
            if source: source.cleanup()
            asyncio.run_coroutine_threadsafe(next_logic(interaction), bot.loop)
            
        vc.play(source, after=after_playing)
        
        # Dashboard Kontrol
        if q.last_dashboard:
            try: await q.last_dashboard.delete()
            except: pass
            
        emb = discord.Embed(title=f"🎶 Sedang Diputar", description=f"**[{data['title']}]({url})**", color=0x2ecc71)
        emb.set_thumbnail(url=data.get('thumbnail'))
        
        # Dashboard ini akan dikirim ke channel sebagai pengganti loading
        q.last_dashboard = await interaction.channel.send(embed=emb, view=MusicDashboard(interaction.guild_id))
        
    except Exception as e:
        print(f"Error: {e}")


# --- 8. COMMANDS ---
@bot.tree.command(name="play", description="Putar musik")
async def play(interaction: discord.Interaction, cari: str):
    await interaction.response.defer()
    if not interaction.user.voice: return await interaction.followup.send("❌ Masuk Voice dulu!")
    if "http" in cari: await play_music(interaction, cari); await interaction.followup.send("✅ Memproses...", ephemeral=True, delete_after=5)
    else:
        data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(f"ytsearch10:{cari}", download=False))
        if not data['entries']: return await interaction.followup.send("❌ Tidak ketemu.")
        embed = discord.Embed(title="🎵 Hasil Pencarian", description="\n".join([f"**{i+1}.** {e['title'][:60]}" for i,e in enumerate(data['entries'])]), color=0x3498db)
        await interaction.followup.send(embed=embed, view=SearchControlView(data['entries'], interaction.user))

@bot.tree.command(name="stop", description="Stop musik & hapus antrean")
async def stop_slash(interaction: discord.Interaction):
    q = get_queue(interaction.guild_id); q.queue.clear()
    if interaction.guild.voice_client: 
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("⏹️ Player dimatikan dan bot keluar dari VC.")
    else: await interaction.response.send_message("❌ Bot tidak berada di Voice Channel.", ephemeral=True)

@bot.tree.command(name="volume", description="Atur Volume")
async def volume(interaction: discord.Interaction, persen: int):
    q = get_queue(interaction.guild_id)
    if 0 <= persen <= 200:
        q.volume = persen / 100
        if interaction.guild.voice_client and interaction.guild.voice_client.source: interaction.guild.voice_client.source.volume = q.volume
        await interaction.response.send_message(f"🔊 Volume: {persen}%")
    else: await interaction.response.send_message("❌ Gunakan angka 0-200", ephemeral=True)

@bot.tree.command(name="pause", description="Jeda musik")
async def pause(interaction: discord.Interaction):
    if interaction.guild.voice_client and interaction.guild.voice_client.is_playing(): interaction.guild.voice_client.pause(); await interaction.response.send_message("⏸️ Musik dijeda.")
    else: await interaction.response.send_message("❌ Tidak ada lagu yang diputar.", ephemeral=True)

@bot.tree.command(name="resume", description="Lanjut musik")
async def resume(interaction: discord.Interaction):
    if interaction.guild.voice_client and interaction.guild.voice_client.is_paused(): interaction.guild.voice_client.resume(); await interaction.response.send_message("▶️ Musik dilanjutkan.")
    else: await interaction.response.send_message("❌ Tidak ada lagu yang dijeda.", ephemeral=True)

@bot.tree.command(name="skip", description="Lewati lagu")
async def skip_cmd(interaction: discord.Interaction):
    if interaction.guild.voice_client: interaction.guild.voice_client.stop(); await interaction.response.send_message("⏭️ Lagu dilewati.")
    else: await interaction.response.send_message("❌ Gak ada lagu.", ephemeral=True)

@bot.tree.command(name="queue", description="Lihat antrean")
async def queue_cmd(interaction: discord.Interaction):
    q = get_queue(interaction.guild_id)
    if not q.queue: return await interaction.response.send_message("📪 Antrean kosong.", delete_after=20)
    emb = discord.Embed(title="📜 Antrean", description="\n".join([f"{i+1}. {x['title']}" for i,x in enumerate(list(q.queue)[:15])]), color=0x9b59b6)
    await interaction.response.send_message(embed=emb, delete_after=20)

@bot.tree.command(name="masuk_vc", description="Panggil bot")
async def masuk(interaction: discord.Interaction):
    if interaction.user.voice: await interaction.user.voice.channel.connect(); await interaction.response.send_message("👋 Bot telah standby!")
    else: await interaction.response.send_message("❌ Masuk Voice dulu!", ephemeral=True)

@bot.tree.command(name="keluar_vc", description="Keluarkan bot")
async def keluar(interaction: discord.Interaction):
    if interaction.guild.voice_client: await interaction.guild.voice_client.disconnect(); await interaction.response.send_message("👋 Bot telah keluar.")

@bot.tree.command(name="help", description="Lihat Panduan & Info Developer")
async def help_cmd(interaction: discord.Interaction):
    dev_id = 590774565115002880
    emb_guide = discord.Embed(title="📖 Panduan Fitur Bot Music", color=0x3498db)
    if bot.user.avatar: emb_guide.set_thumbnail(url=bot.user.avatar.url)
    emb_guide.description = (
        "🎵 **KONTROL UTAMA**\n"
        "┕ 🔘 `/play` - Putar musik via judul/link\n"
        "┕ ⏭️ `/skip` - Lewati lagu yang diputar\n"
        "┕ ⏹️ `/stop` - Matikan musik & hapus antrean\n"
        "┕ 📜 `/queue`- Lihat daftar lagu mengantre\n\n"
        "⚙️ **SISTEM & VOLUME**\n"
        "┕ 🔊 `/volume` - Atur level suara (0-200%)\n"
        "┕ 📥 `/masuk_vc`  - Panggil bot ke Voice Channel\n"
        "┕ 📤 `/keluar_vc` - Keluarkan bot dari Voice Channel\n\n"
        "✨ **FITUR DASHBOARD INTERAKTIF**\n"
        "┕ ⏯️ **Pause/Resume** : Jeda atau lanjut lagu\n"
        "┕ 🔊 **Volume Mixer** : Atur suara lewat tombol\n"
        "┕ 📜 **Smart Queue** : Pilih & lompat antrean lagu\n"
        "┕ ⏭️ **Quick Skip** : Lewati lagu tanpa ngetik"
    )
    emb_dev = discord.Embed(title="👨‍💻 Developer Profile", color=0x9b59b6)
    emb_dev.description = (f"**Developer :** ikiii\n**User ID :** `{dev_id}`\n**Status :** Active - IT - Engineering\n**Contact :** <@{dev_id}>\n\n**Kata - kata :**\nBot ini dibuat oleh seorang yang bernama **ikiii** yang bijaksana, dan yang melakukan segala hal apapun diawali dengan berdo'a 🤲🏻, amiin.")
    emb_dev.set_image(url="https://i.getpantry.cloud/apf/help_banner.gif")
    emb_dev.set_footer(text="Bot Bot • ikiii angels Project v16", icon_url=interaction.user.display_avatar.url)
    await interaction.response.send_message(embeds=[emb_guide, emb_dev])

bot.run(TOKEN)
