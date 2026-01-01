
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
    'options': '-vn -b:a 128k -threads 2' # Menghapus loudnorm & menurunkan bitrate agar tidak buffer
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


# --- TAMBAHAN: NOTIFIKASI BOT ONLINE (AUTO-CLEAN + FULL INFO) ---
@bot.event
async def on_ready():
    # ID Channel 
    target_channel_id = 1456250414638043169 
    
    channel = bot.get_channel(target_channel_id)
    if channel:
        # --- FITUR PEMBERSIH ---
        try:
            async for message in channel.history(limit=10):
                if message.author == bot.user:
                    await message.delete()
        except Exception as e:
            print(f"Gagal menghapus pesan lama: {e}")

        # --- KIRIM PESAN BARU ---
        embed = discord.Embed(
            title="🚀 SYSTEM RELOADED & UPDATED",
            description="**Bot telah online dan berhasil di update!**\nBot audio Angelss siap digunakan dengan baik.",
            color=0x2ecc71 
        )
        
        # Menambahkan Banner Visual
        embed.set_image(url="https://i.getpantry.cloud/apf/help_banner.gif")
        
        # Informasi Server, Latency, dan Guide 
        embed.add_field(name="🛰️ Server Cluster", value="`Jakarta-ID`", inline=True)
        embed.add_field(name="⚡ Latency", value=f"`{round(bot.latency * 1000)}ms`", inline=True)
        embed.add_field(name="💡 Guide", value="Ketik `/help` untuk panduan", inline=False)
        
        # Menambahkan informasi waktu update terakhir agar makin keren
        waktu_sekarang = discord.utils.utcnow().astimezone(discord.utils.utc).strftime('%d/%m/%Y %H:%M')
        embed.add_field(name="📅 Terakhir Diupdate", value=f"`{waktu_sekarang} WIB`", inline=False)

        embed.set_footer(
            text="System Online • ikiii angels Project v16", 
            icon_url=bot.user.avatar.url if bot.user.avatar else None
        )
        embed.set_thumbnail(url="https://i.gifer.com/7plQ.gif") 
        
        await channel.send(embed=embed)
    
    print(f"✅ Logged in as {bot.user} - Notifikasi Lengkap Terkirim!")


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
            # --- PERBAIKAN LOGIKA CHANNEL DI SINI ---
            # Kita ambil data queue untuk tahu dimana dashboard terakhir muncul
            q = get_queue(member.guild.id)
            msg_chan = None

            # Prioritas 1: Kirim ke channel tempat Dashboard Musik berada (paling akurat)
            if q.last_dashboard:
                msg_chan = q.last_dashboard.channel
            
            # Prioritas 2: Jika dashboard tidak ada, cari text channel pertama di kategori voice tersebut
            elif before.channel.category:
                for channel in before.channel.category.text_channels:
                    # Pastikan bot punya izin kirim pesan di situ
                    if channel.permissions_for(member.guild.me).send_messages:
                        msg_chan = channel
                        break
            
            # Kirim pesan peringatan jika channel ditemukan
            if msg_chan:
                await msg_chan.send("⚠️ **Informasi:** Tidak ada pengguna di Voice Channel. Bot akan otomatis keluar dalam **30 detik**.", delete_after=30)
            
            # --- BAGIAN PENGATURAN WAKTU (TIMER) ---
            # Ubah angka 15 di bawah ini jika ingin mengganti durasi (misal 60 untuk 1 menit)
            await asyncio.sleep(30) 
            
            # Cek lagi setelah waktu habis, apakah masih sendirian?
            if vc and vc.channel and len(vc.channel.members) == 1:
                q = get_queue(member.guild.id)
                q.queue.clear() # Hapus antrean
                await vc.disconnect() # Cabut dari voice


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



# --- 7. CORE LOGIC (FIXED ORDER & CLEANUP) ---

async def next_logic(interaction):
    """Logika untuk memutar lagu berikutnya di antrean"""
    q = get_queue(interaction.guild_id)
    if q.queue:
        next_song = q.queue.popleft()
        await start_stream(interaction, next_song['url'])
    else:
        # Bersihkan dashboard jika antrean habis
        if q.last_dashboard:
            try: await q.last_dashboard.delete()
            except: pass
            q.last_dashboard = None
        await interaction.channel.send("✅ Antrean selesai.", delete_after=10)

async def start_stream(interaction, url):
    """Fungsi utama untuk streaming audio dari YouTube"""
    q = get_queue(interaction.guild_id)
    vc = interaction.guild.voice_client
    if not vc: return
    
    try:
        # 1. Paksa hentikan audio sebelumnya jika masih berjalan
        if vc.is_playing() or vc.is_paused():
            vc.stop()
            await asyncio.sleep(0.8) # Jeda agar FFmpeg benar-benar mati

        # 2. Ambil data dari YT-DLP
        data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
        
        # 3. Setup Audio Source
        source = discord.PCMVolumeTransformer(
            discord.FFmpegPCMAudio(data['url'], **FFMPEG_OPTIONS), 
            volume=q.volume
        )
        
        # 4. Fungsi Callback setelah lagu selesai
        def after_playing(error):
            if error: print(f"Player error: {error}")
            # Jalankan antrean berikutnya
            asyncio.run_coroutine_threadsafe(next_logic(interaction), bot.loop)
            
        vc.play(source, after=after_playing)
        
        # 5. Update UI Dashboard
        if q.last_dashboard:
            try: await q.last_dashboard.delete()
            except: pass
            
        emb = discord.Embed(title=f"🎶 Sedang Diputar", description=f"**[{data['title']}]({url})**", color=0x2ecc71)
        emb.set_thumbnail(url=data.get('thumbnail'))
        
        q.last_dashboard = await interaction.channel.send(embed=emb, view=MusicDashboard(interaction.guild_id))
        
    except Exception as e:
        print(f"Error pada start_stream: {e}")
        await interaction.channel.send(f"❌ Terjadi kesalahan saat memutar: {e}", delete_after=10)

async def play_music(interaction, url):
    """Fungsi kontrol untuk play langsung atau masuk queue"""
    q = get_queue(interaction.guild_id)
    
    if not interaction.guild.voice_client:
        if interaction.user.voice:
            await interaction.user.voice.channel.connect()
        else:
            return await interaction.channel.send("❌ Kamu harus di Voice Channel!")
    
    vc = interaction.guild.voice_client
    
    if vc.is_playing() or vc.is_paused():
        data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
        q.queue.append({'title': data['title'], 'url': url})
        emb = discord.Embed(description=f"✅ **Berhasil Masuk Antrean:**\n{data['title']}", color=0x3498db)
        
        # FIX: Followup tidak boleh pakai delete_after
        if interaction.response.is_done():
            await interaction.followup.send(embed=emb, ephemeral=True)
        else:
            await interaction.response.send_message(embed=emb, ephemeral=True, delete_after=20)
    else:
        # Menghilangkan status "Thinking"
        msg = "🎶 **Memproses lagu...**"
        if not interaction.response.is_done():
            await interaction.response.send_message(msg, ephemeral=True, delete_after=5)
        else:
            await interaction.followup.send(msg, ephemeral=True)
            
        await start_stream(interaction, url)



# --- 8. COMMANDS ---
@bot.tree.command(name="play", description="Putar musik")
async def play(interaction: discord.Interaction, cari: str):
    await interaction.response.defer()
    if not interaction.user.voice: 
        return await interaction.followup.send("❌ Masuk Voice dulu!", ephemeral=True)
    
    if "http" in cari: 
        await play_music(interaction, cari)
        # FIX: Hapus delete_after di sini
        await interaction.followup.send("✅ Permintaan diproses!", ephemeral=True)
    else:
        data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(f"ytsearch10:{cari}", download=False))
        if not data['entries']: 
            return await interaction.followup.send("❌ Tidak ketemu.", ephemeral=True)
            
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
    emb_guide = discord.Embed(title="📖 Panduan Fitur Bot Music Angelss", color=0x3498db)
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
    emb_dev.set_footer(text="Projects Bot • Music Ikiii hehehe ....", icon_url=interaction.user.display_avatar.url)
    await interaction.response.send_message(embeds=[emb_guide, emb_dev])

bot.run(TOKEN)
