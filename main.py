import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import asyncio
import os
from collections import deque

# --- 1. KONFIGURASI GLOBAL (TETAP OPTIMAL - TIDAK DIRUBAH) ---
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
        print("✅ SISTEM V16 (ADVANCED QUEUE & DYNAMIC UI) ONLINE!")

bot = ModernBot()

# --- 3. QUEUE SYSTEM (TETAP) ---
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

# --- 4. UI: VOLUME MIXER (TETAP) ---
class VolumeControlView(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=60)
        self.guild_id = guild_id

    def create_embed(self):
        q = get_queue(self.guild_id)
        vol_percent = int(q.volume * 100)
        embed = discord.Embed(title="🎚️ Pengaturan Audio", color=0x3498db)
        bar = "▰" * (vol_percent // 20) + "▱" * (max(0, 5 - (vol_percent // 20)))
        embed.description = f"Volume Saat Ini: **{vol_percent}%**\n`{bar}`"
        return embed

    @discord.ui.button(label="-20%", style=discord.ButtonStyle.danger, emoji="🔉")
    async def down(self, interaction: discord.Interaction, button: discord.ui.Button):
        q = get_queue(self.guild_id)
        q.volume = max(0.0, q.volume - 0.2)
        if interaction.guild.voice_client and interaction.guild.voice_client.source:
            interaction.guild.voice_client.source.volume = q.volume
        await interaction.response.edit_message(embed=self.create_embed())

    @discord.ui.button(label="+20%", style=discord.ButtonStyle.success, emoji="🔊")
    async def up(self, interaction: discord.Interaction, button: discord.ui.Button):
        q = get_queue(self.guild_id)
        q.volume = min(2.0, q.volume + 0.2)
        if interaction.guild.voice_client and interaction.guild.voice_client.source:
            interaction.guild.voice_client.source.volume = q.volume
        await interaction.response.edit_message(embed=self.create_embed())

# --- 5. UI: DYNAMIC DASHBOARD (TETAP) ---
class MusicDashboard(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.button(label="Jeda", emoji="⏸️", style=discord.ButtonStyle.secondary)
    async def pp(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if not vc: return
        if vc.is_playing():
            vc.pause()
            button.emoji = "▶️"
            button.label = "Lanjut"
            button.style = discord.ButtonStyle.success 
        else:
            vc.resume()
            button.emoji = "⏸️"
            button.label = "Jeda"
            button.style = discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Volume", emoji="🔊", style=discord.ButtonStyle.gray)
    async def vol(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = VolumeControlView(self.guild_id)
        await interaction.response.send_message(embed=view.create_embed(), view=view, ephemeral=True)

    @discord.ui.button(label="Antrean", emoji="📜", style=discord.ButtonStyle.gray)
    async def list_q(self, interaction: discord.Interaction, button: discord.ui.Button):
        q = get_queue(self.guild_id)
        if not q.queue:
            return await interaction.response.send_message("📪 Antrean kosong.", ephemeral=True)
        
        emb = discord.Embed(title="📜 Antrean Musik Saat Ini", color=0x2b2d31)
        description = ""
        options = []
        for i, item in enumerate(list(q.queue)[:10]):
            description += f"**{i+1}.** {item['title'][:50]}...\n"
            options.append(discord.SelectOption(label=f"{i+1}. {item['title'][:25]}", value=str(i), description="Klik untuk putar lagu ini"))
        
        emb.description = description
        emb.set_footer(text="Gunakan menu di bawah untuk melompati antrean.")
        select = discord.ui.Select(placeholder="🎯 Pilih lagu untuk langsung diputar...", options=options)

        async def select_callback(inter: discord.Interaction):
            idx = int(select.values[0]); chosen = q.queue[idx]
            del q.queue[idx]; q.queue.appendleft(chosen)
            if inter.guild.voice_client: inter.guild.voice_client.stop()
            await inter.response.send_message(f"🚀 Memutar: **{chosen['title']}**", ephemeral=True)

        select.callback = select_callback
        view = discord.ui.View(); view.add_item(select)
        await interaction.response.send_message(embed=emb, view=view, ephemeral=True)

    @discord.ui.button(label="Skip", emoji="⏭️", style=discord.ButtonStyle.primary)
    async def sk(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild.voice_client: 
            interaction.guild.voice_client.stop()
            await interaction.response.send_message("⏭️ Lagu dilewati!", ephemeral=True)

    @discord.ui.button(label="Stop", emoji="⏹️", style=discord.ButtonStyle.danger)
    async def st(self, interaction: discord.Interaction, button: discord.ui.Button):
        q = get_queue(self.guild_id)
        q.queue.clear()
        if interaction.guild.voice_client: 
            interaction.guild.voice_client.stop()
            await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("⏹️ Player dimatikan.", ephemeral=True)

# --- 6. CORE LOGIC (TETAP) ---
async def start_stream(interaction, url):
    q = get_queue(interaction.guild_id)
    vc = interaction.guild.voice_client
    try:
        data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
        source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(data['url'], **FFMPEG_OPTIONS), volume=q.volume)
        q.current_info = {'title': data['title'], 'url': url, 'thumb': data.get('thumbnail'), 'dur': data.get('duration')}
        def after_playing(error):
            coro = next_logic(interaction)
            asyncio.run_coroutine_threadsafe(coro, bot.loop)
        vc.play(source, after=after_playing)
        if q.last_dashboard:
            try: await q.last_dashboard.delete()
            except: pass
        emb = discord.Embed(color=0x2f3136)
        emb.set_author(name="NOW PLAYING", icon_url="https://i.getpantry.cloud/apf/music_icon.gif")
        emb.title = f"✨ {data['title']}"; emb.url = url
        emb.set_thumbnail(url=data.get('thumbnail'))
        dur_str = f"{data.get('duration')//60:02d}:{data.get('duration')%60:02d}"
        emb.add_field(name="👤 Request", value=f"{interaction.user.mention}", inline=True)
        emb.add_field(name="⏱️ Durasi", value=f"`{dur_str}`", inline=True)
        emb.add_field(name="🎧 Audio", value="`HQ 320kbps`", inline=True)
        emb.add_field(name="Progress", value="`🔘▬▬▬▬▬▬▬▬▬▬`", inline=False)
        q.last_dashboard = await interaction.channel.send(embed=emb, view=MusicDashboard(interaction.guild_id))
    except Exception as e: await interaction.channel.send(f"❌ Error: {e}")

async def next_logic(interaction):
    q = get_queue(interaction.guild_id)
    vc = interaction.guild.voice_client
    if not vc or not vc.is_connected(): return
    await asyncio.sleep(1.5)
    if q.loop and q.current_info: await start_stream(interaction, q.current_info['url'])
    elif q.queue:
        next_song = q.queue.popleft()
        await start_stream(interaction, next_song['url'])
    else:
        q.current_info = None
        if q.last_dashboard:
            try: await q.last_dashboard.delete()
            except: pass
        await interaction.channel.send("✅ Antrean selesai.", delete_after=10)

async def play_music(interaction, url):
    q = get_queue(interaction.guild_id)
    if not interaction.guild.voice_client: await interaction.user.voice.channel.connect()
    vc = interaction.guild.voice_client
    if vc.is_playing() or vc.is_paused():
        data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
        q.queue.append({'title': data['title'], 'url': url})
        emb = discord.Embed(description=f"✅ **Ditambahkan:** [{data['title']}]({url})", color=0x2ecc71)
        return await interaction.followup.send(embed=emb, ephemeral=True)
    await start_stream(interaction, url)

# --- 7. COMMANDS ---

@bot.tree.command(name="play", description="Putar musik")
async def play(interaction: discord.Interaction, cari: str):
    await interaction.response.defer()
    if not interaction.user.voice: return await interaction.followup.send("❌ Masuk VC dulu!", ephemeral=True)
    if "http" in cari:
        await play_music(interaction, cari)
        await interaction.followup.send("✅ Memproses...", ephemeral=True)
    else:
        data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(f"ytsearch1:{cari}", download=False))
        if not data['entries']: return await interaction.followup.send("❌ Tidak ditemukan.")
        await play_music(interaction, data['entries'][0]['webpage_url'])
        await interaction.followup.send(f"🔍 Menemukan: **{data['entries'][0]['title']}**", ephemeral=True)

@bot.tree.command(name="help", description="Lihat Panduan Cara Menggunakan Bot Ini")
async def help_cmd(interaction: discord.Interaction):
    dev_user = "ikiii" 
    dev_id = interaction.client.application.owner.id if interaction.client.application.owner else "779745719321722881"

    
    if bot.user.avatar: embed.set_thumbnail(url=bot.user.avatar.url)
	
	emb_guide = discord.Embed(title="📖 Panduan Fitur Bot Music", color=0x3498db)
    emb_guide.description = (
        "🎵 **KONTROL UTAMA**\n"
        "┕ 🔘 `/play` - Putar musik via judul/link\n"
        "┕ ⏭️ `/skip` - Lewati lagu yang diputar\n"
        "┕ ⏹️ `/stop` - Matikan musik & hapus antrean\n"
        "┕ 📜 `/queue`- Lihat daftar lagu mengantre"
       
        
        "\n\n⚙️ **SISTEM & VOLUME**\n"
        "┕ 🔊 `/volume` - Atur level suara (0-200%)\n"
        "┕ 📥 `/masuk`  - Panggil bot ke Voice Channel\n"
        "┕ 📤 `/keluar` - Keluarkan bot dari Voice Channel"
        
        "\n\n✨ **FITUR DASHBOARD INTERAKTIF**\n"
        "┕ ⏯️ **Pause/Resume** : Jeda atau lanjut lagu\n"
        "┕ 🔊 **Volume Mixer** : Atur suara lewat tombol\n"
        "┕ 📜 **Smart Queue** : Pilih & lompat antrean lagu\n"
        "┕ ⏭️ **Quick Skip** : Lewati lagu tanpa ngetik"
        )
   
    emb_dev = discord.Embed(title="👨‍💻 Developer Profile", color=0x9b59b6)
    emb_dev.description = (
            f"Developer : {dev_user}\n"
            f"User ID   : {dev_id}\n"
            f"Status    : Active - IT - Engineering\n"
            f"Kata - kata :  \n"
            "Bot ini dibuat oleh seorang yang bernama **ikiii** yang bijaksana, "
            "dan yang melakukan segala hal apapun diawali dengan berdo'a 🤲🏻, amiin.\n\n"
     )
     embed_dev.set_footer(text="Bot Bt • ikiii angels Project v16", icon_url=interaction.user.display_avatar.url)
     embed_dev.set_image(url="https://i.getpantry.cloud/apf/help_banner.gif")

    await interaction.response.send_message(embeds=[emb_guide, emb_dev])
    

@bot.tree.command(name="masuk VC", description="Masukkan Bot Ke Voice")
async def masuk(interaction: discord.Interaction):
    if interaction.user.voice:
        await interaction.user.voice.channel.connect()
        await interaction.response.send_message("👋 Halo! Saya sudah standby di VC.")
    else: await interaction.response.send_message("❌ Masuk VC dulu!", ephemeral=True)

@bot.tree.command(name="keluar VC", description="Kekuarkan Bot Dari Voice")
async def keluar(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        get_queue(interaction.guild_id).queue.clear()
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("👋 Sampai jumpa lagi!")
    else: await interaction.response.send_message("❌ Aku sedang tidak di VC.", ephemeral=True)

@bot.tree.command(name="volume", description="Untuk Mengatur Volume")
async def volume(interaction: discord.Interaction, persen: int):
    q = get_queue(interaction.guild_id)
    if 0 <= persen <= 200:
        q.volume = persen / 100
        if interaction.guild.voice_client and interaction.guild.voice_client.source:
            interaction.guild.voice_client.source.volume = q.volume
        await interaction.response.send_message(f"🔊 Volume berhasil diubah ke: **{persen}%**")
    else: await interaction.response.send_message("❌ Gunakan angka 0-200.", ephemeral=True)

@bot.tree.command(name="skip", description="Lewati lagu")
async def skip_slash(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("⏭️ Lagu berhasil dilewati.")
    else: await interaction.response.send_message("❌ Tidak ada lagu.", ephemeral=True)

@bot.tree.command(name="stop", description="Berhenti memutar musik")
async def stop_slash(interaction: discord.Interaction):
    q = get_queue(interaction.guild_id)
    q.queue.clear()
    if interaction.guild.voice_client:
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("⏹️ Musik dihentikan dan antrean dihapus.")
    else: await interaction.response.send_message("❌ Bot tidak sedang memutar lagu.", ephemeral=True)

@bot.tree.command(name="queue")
async def queue_slash(interaction: discord.Interaction):
    q = get_queue(interaction.guild_id)
    if not q.queue: return await interaction.response.send_message("📪 Antrean kosong.")
    emb = discord.Embed(title="📜 Antrean Musik", description="\n".join([f"**{i+1}.** {item['title']}" for i, item in enumerate(list(q.queue)[:15])]), color=0x9b59b6)
    await interaction.response.send_message(embed=emb)

bot.run(TOKEN)
