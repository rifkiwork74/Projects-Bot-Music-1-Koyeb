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

# PERTAHANKAN SETTINGAN INI (JANGAN DIUBAH)
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -b:a 320k' 
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
        print("✅ SISTEM V12 (DYNAMIC UI) ONLINE!")

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
        embed = discord.Embed(title="🔊 Pengaturan Suara", color=0x3498db)
        embed.description = f"Volume sekarang: **{vol_percent}%**"
        bar = "🟦" * (vol_percent // 10) + "⬜" * (max(0, 10 - (vol_percent // 10)))
        embed.add_field(name="Indikator", value=bar)
        return embed

    @discord.ui.button(label="-10%", style=discord.ButtonStyle.danger, emoji="➖")
    async def down(self, interaction: discord.Interaction, button: discord.ui.Button):
        q = get_queue(self.guild_id)
        q.volume = max(0.0, q.volume - 0.1)
        if interaction.guild.voice_client and interaction.guild.voice_client.source:
            interaction.guild.voice_client.source.volume = q.volume
        await interaction.response.edit_message(embed=self.create_embed())

    @discord.ui.button(label="+10%", style=discord.ButtonStyle.success, emoji="➕")
    async def up(self, interaction: discord.Interaction, button: discord.ui.Button):
        q = get_queue(self.guild_id)
        q.volume = min(2.0, q.volume + 0.1)
        if interaction.guild.voice_client and interaction.guild.voice_client.source:
            interaction.guild.voice_client.source.volume = q.volume
        await interaction.response.edit_message(embed=self.create_embed())

# --- 5. UI: SEARCH PAGINATION ---
class SearchView(discord.ui.View):
    def __init__(self, results, interaction_user):
        super().__init__(timeout=60)
        self.results = results
        self.user = interaction_user
        self.page = 0

    def create_embed(self):
        start = self.page * 5
        current_list = self.results[start:start+5]
        embed = discord.Embed(title="🔍 Katalog Musik", color=0x2b2d31, description="Gunakan tombol di bawah untuk navigasi halaman.")
        for i, res in enumerate(current_list):
            dur = f"{res.get('duration')//60}:{res.get('duration')%60:02d}"
            embed.add_field(name=f"{start+i+1}. {res['title'][:60]}", value=f"🕒 Durasi: {dur} | 👤 {res['uploader']}", inline=False)
        embed.set_footer(text=f"Halaman {self.page+1}/3 • Pilih nomor lagu di bawah")
        return embed

    @discord.ui.button(label="⬅️ Kembali", style=discord.ButtonStyle.gray)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
            await interaction.response.edit_message(embed=self.create_embed())

    @discord.ui.button(label="Lanjut ➡️", style=discord.ButtonStyle.gray)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page < 2:
            self.page += 1
            await interaction.response.edit_message(embed=self.create_embed())

    @discord.ui.button(label="Pilih Lagu", style=discord.ButtonStyle.green)
    async def select(self, interaction: discord.Interaction, button: discord.ui.Button):
        options = [discord.SelectOption(label=f"Lagu Nomor {i+1}", value=str(i)) for i in range(self.page*5, (self.page*5)+5)]
        sel = discord.ui.Select(placeholder="Klik untuk memilih nomor...", options=options)
        async def callback(inter: discord.Interaction):
            await inter.response.defer()
            await play_music(inter, self.results[int(sel.values[0])]['url'])
        sel.callback = callback
        v = discord.ui.View(); v.add_item(sel)
        await interaction.response.send_message("Konfirmasikan pilihanmu:", view=v, ephemeral=True)

# --- 6. UI: DYNAMIC DASHBOARD (FITUR BARU) ---
class MusicDashboard(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        # Default state saat baru play adalah 'Pause' (tombol Jeda aktif)
        # Karena musik sedang jalan

    @discord.ui.button(label="Jeda", emoji="⏸️", style=discord.ButtonStyle.secondary)
    async def pp(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if not vc: return await interaction.response.send_message("Bot tidak terhubung.", ephemeral=True)

        if vc.is_playing():
            # Jika sedang main, kita PAUSE
            vc.pause()
            # Ganti tombol jadi PLAY (Resume)
            button.emoji = "▶️"
            button.label = "Lanjut"
            button.style = discord.ButtonStyle.success # Ubah warna jadi hijau biar jelas
        else:
            # Jika sedang pause, kita RESUME
            vc.resume()
            # Ganti tombol jadi PAUSE (Jeda)
            button.emoji = "⏸️"
            button.label = "Jeda"
            button.style = discord.ButtonStyle.secondary # Balik ke warna abu/secondary

        # Update tampilan tombolnya
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Volume", emoji="🔊", style=discord.ButtonStyle.gray)
    async def vol(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = VolumeControlView(self.guild_id)
        await interaction.response.send_message(embed=view.create_embed(), view=view, ephemeral=True)

    @discord.ui.button(label="Loop", emoji="🔁", style=discord.ButtonStyle.gray)
    async def lp(self, interaction: discord.Interaction, button: discord.ui.Button):
        q = get_queue(self.guild_id)
        q.loop = not q.loop
        button.style = discord.ButtonStyle.success if q.loop else discord.ButtonStyle.gray
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Skip", emoji="⏭️", style=discord.ButtonStyle.primary)
    async def sk(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild.voice_client: interaction.guild.voice_client.stop()
        await interaction.response.send_message("⏭️ Berhasil dilewati!", ephemeral=True)

    @discord.ui.button(label="Stop", emoji="🛑", style=discord.ButtonStyle.danger)
    async def st(self, interaction: discord.Interaction, button: discord.ui.Button):
        q = get_queue(self.guild_id)
        q.queue.clear()
        if interaction.guild.voice_client: 
            interaction.guild.voice_client.stop()
            await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("🛑 Media Player Dimatikan.", ephemeral=True)

# --- 7. CORE LOGIC ---
async def play_music(interaction, url):
    q = get_queue(interaction.guild_id)
    
    # Auto Join Logic
    if not interaction.guild.voice_client:
        if interaction.user.voice:
            await interaction.user.voice.channel.connect()
        else:
            return await interaction.followup.send("❌ Masuk Voice Channel dulu!", ephemeral=True)
    
    vc = interaction.guild.voice_client
    
    # Logic Antrean
    if vc.is_playing() or vc.is_paused():
        data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
        q.queue.append(url)
        embed = discord.Embed(title="📥 Berhasil Masuk Antrean", description=f"**[{data['title']}]({url})**", color=0x2ecc71)
        embed.set_thumbnail(url=data.get('thumbnail'))
        embed.set_footer(text="Posisi: Paling belakang")
        return await interaction.followup.send(embed=embed, ephemeral=True)
    
    await start_stream(interaction, url)

async def start_stream(interaction, url):
    q = get_queue(interaction.guild_id)
    vc = interaction.guild.voice_client
    
    try:
        data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
        source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(data['url'], **FFMPEG_OPTIONS), volume=q.volume)
        q.current_info = {'title': data['title'], 'url': url, 'thumb': data.get('thumbnail')}
        
        def after_playing(error):
            if error: print(f"Error: {error}")
            coro = next_logic(interaction)
            fut = asyncio.run_coroutine_threadsafe(coro, bot.loop)
            try: fut.result()
            except: pass

        vc.play(source, after=after_playing)
        
        if q.last_dashboard:
            try: await q.last_dashboard.delete()
            except: pass

        emb = discord.Embed(title="🎶 Musik Sedang Diputar", description=f"**[{data['title']}]({url})**", color=0x5865F2)
        emb.set_thumbnail(url=data.get('thumbnail'))
        emb.add_field(name="Pengirim", value=f"<@{interaction.user.id}>", inline=True)
        emb.add_field(name="Kualitas", value="✨ 320kbps Max", inline=True)
        
        # Panggil Dynamic Dashboard
        q.last_dashboard = await interaction.channel.send(embed=emb, view=MusicDashboard(interaction.guild_id))
    except Exception as e:
        await interaction.channel.send(f"❌ Error Audio: {e}")

async def next_logic(interaction):
    q = get_queue(interaction.guild_id)
    vc = interaction.guild.voice_client
    if not vc or not vc.is_connected(): return
    
    if q.loop and q.current_info:
        await start_stream(interaction, q.current_info['url'])
    elif q.queue:
        await start_stream(interaction, q.queue.popleft())
    else:
        q.current_info = None
        embed = discord.Embed(title="🏁 Antrean Selesai", description="Menunggu lagu berikutnya...", color=0xe67e22)
        await interaction.channel.send(embed=embed, delete_after=10)

# --- 8. AUTO DISCONNECT ---
@bot.event
async def on_voice_state_update(member, before, after):
    if member.id == bot.user.id: return
    if before.channel is not None:
        vc = member.guild.voice_client
        if vc and vc.channel.id == before.channel.id and len(before.channel.members) == 1:
            q = get_queue(member.guild_id)
            await asyncio.sleep(60) 
            if len(before.channel.members) == 1:
                await vc.disconnect()
                q.queue.clear()
                q.current_info = None
                await member.guild.system_channel.send("👋 Keluar otomatis karena sepi.")

# --- 9. SLASH COMMANDS (RENAMED) ---

@bot.tree.command(name="masuk", description="Bot akan masuk ke Voice Channel")
async def masuk(interaction: discord.Interaction):
    if interaction.user.voice:
        channel = interaction.user.voice.channel
        await channel.connect()
        await interaction.response.send_message(f"✅ Berhasil masuk ke **{channel.name}**")
    else:
        await interaction.response.send_message("❌ Kamu harus masuk VC dulu!", ephemeral=True)

@bot.tree.command(name="keluar", description="Bot akan keluar dari Voice Channel")
async def keluar(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        q = get_queue(interaction.guild_id)
        q.queue.clear()
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("👋 Berhasil keluar.")
    else:
        await interaction.response.send_message("❌ Bot tidak ada di dalam VC.", ephemeral=True)

@bot.tree.command(name="help", description="Daftar perintah bot")
async def help_cmd(interaction: discord.Interaction):
    emb_guide = discord.Embed(title="📖 Daftar Perintah", color=0x3498db)
    emb_guide.description = (
        "**Perintah Utama:**\n"
        "1. `/play` : Putar musik (Link/Cari Judul)\n"
        "2. `/masuk` : Panggil bot ke VC\n"
        "3. `/keluar` : Usir bot dari VC\n"
        "4. `/stop` : Berhenti & Hapus antrean\n\n"
        "**Kontrol Musik:**\n"
        "• `/pause` & `/resume`\n"
        "• `/skip` : Lewati lagu\n"
        "• `/loop` : Ulangi lagu\n"
        "• `/volume` : Atur suara 0-200"
    )
    emb_dev = discord.Embed(title="👨‍💻 Informasi Author", color=0x9b59b6)
    emb_dev.description = (
        "Bot ini dibuat oleh **ikiii** yang bijaksana, "
        "dan yang melakukan segala hal apapun diawali dengan berdo'a 🤲🏻, amiin.\n\n"
        "🔗 **Profil Developer:** <@590774565115002880>"
    )
    await interaction.response.send_message(embeds=[emb_guide, emb_dev])

@bot.tree.command(name="play", description="Putar musik favoritmu")
async def play(interaction: discord.Interaction, cari: str):
    await interaction.response.defer()
    if not interaction.user.voice: return await interaction.followup.send("❌ Masuk VC dulu!", ephemeral=True)
    
    if "http" in cari:
        await play_music(interaction, cari)
        embed = discord.Embed(title="🔗 Memproses Link", description="Sedang mengambil data dari URL YouTube...", color=0x9b59b6)
        await interaction.followup.send(embed=embed, ephemeral=True)
    else:
        embed_load = discord.Embed(title="🔍 Sedang Mencari...", description=f"Mencari lagu untuk: `{cari}`", color=0xf1c40f)
        msg = await interaction.followup.send(embed=embed_load)
        
        data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(f"ytsearch15:{cari}", download=False))
        view = SearchView(data['entries'], interaction.user)
        await msg.edit(embed=view.create_embed(), view=view)

@bot.tree.command(name="stop", description="Hentikan semua musik")
async def stop(interaction: discord.Interaction):
    q = get_queue(interaction.guild_id)
    q.queue.clear()
    if interaction.guild.voice_client: 
        interaction.guild.voice_client.stop()
        await interaction.guild.voice_client.disconnect()
    await interaction.response.send_message("🛑 Musik dihentikan.")

@bot.tree.command(name="pause", description="Jeda musik")
async def pause(interaction: discord.Interaction):
    if interaction.guild.voice_client: interaction.guild.voice_client.pause()
    await interaction.response.send_message("⏸️ Musik dijeda.")

@bot.tree.command(name="resume", description="Lanjutkan musik")
async def resume(interaction: discord.Interaction):
    if interaction.guild.voice_client: interaction.guild.voice_client.resume()
    await interaction.response.send_message("▶️ Musik dilanjutkan.")

@bot.tree.command(name="volume", description="Atur suara (0-200)")
async def volume(interaction: discord.Interaction, persen: int):
    q = get_queue(interaction.guild_id)
    if 0 <= persen <= 200:
        q.volume = persen / 100
        if interaction.guild.voice_client and interaction.guild.voice_client.source:
            interaction.guild.voice_client.source.volume = q.volume
        await interaction.response.send_message(f"🔊 Volume berhasil diatur ke **{persen}%**")
    else:
        await interaction.response.send_message("❌ Pilih angka antara 0 hingga 200!", ephemeral=True)

@bot.tree.command(name="loop", description="Toggle loop lagu")
async def loop_cmd(interaction: discord.Interaction):
    q = get_queue(interaction.guild_id)
    q.loop = not q.loop
    await interaction.response.send_message(f"🔁 Loop: **{'AKTIF' if q.loop else 'NONAKTIF'}**")

@bot.tree.command(name="skip", description="Lewati lagu")
async def skip_cmd(interaction: discord.Interaction):
    if interaction.guild.voice_client: 
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("⏭️ Lagu dilewati.")
    else:
        await interaction.response.send_message("❌ Tidak ada lagu.", ephemeral=True)

bot.run(TOKEN)
