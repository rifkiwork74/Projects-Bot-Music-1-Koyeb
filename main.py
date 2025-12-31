import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import asyncio
import os
from collections import deque

# --- 1. KONFIGURASI ---
TOKEN = os.environ['DISCORD_TOKEN']
COOKIES_FILE = 'youtube_cookies.txt'

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

# --- 2. SETUP BOT ---
class ModernBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print("✅ Semua Slash Commands (Termasuk Loop) telah disinkronkan!")

bot = ModernBot()

# --- 3. STORAGE SYSTEM ---
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

# --- 4. UI: SEARCH PAGINATION ---
class SearchView(discord.ui.View):
    def __init__(self, results, interaction_user):
        super().__init__(timeout=60)
        self.results = results
        self.user = interaction_user
        self.page = 0

    def create_embed(self):
        start = self.page * 5
        current_list = self.results[start:start+5]
        embed = discord.Embed(title="🔍 Music Directory", color=0x2b2d31)
        for i, res in enumerate(current_list):
            dur = f"{res.get('duration')//60}:{res.get('duration')%60:02d}"
            embed.add_field(name=f"{start+i+1}. {res['title'][:60]}", value=f"👤 {res['uploader']} | 🕒 {dur}", inline=False)
        return embed

    @discord.ui.button(label="⬅️ Back", style=discord.ButtonStyle.gray)
    async def prev(self, interaction: discord.Interaction):
        if self.page > 0:
            self.page -= 1
            await interaction.response.edit_message(embed=self.create_embed())

    @discord.ui.button(label="Next ➡️", style=discord.ButtonStyle.gray)
    async def next(self, interaction: discord.Interaction):
        if self.page < 2:
            self.page += 1
            await interaction.response.edit_message(embed=self.create_embed())

    @discord.ui.button(label="Play Lagu", style=discord.ButtonStyle.green)
    async def select(self, interaction: discord.Interaction):
        options = [discord.SelectOption(label=f"Lagu {i+1}", value=str(i)) for i in range(self.page*5, (self.page*5)+5)]
        sel = discord.ui.Select(placeholder="Pilih nomor lagu...", options=options)
        async def callback(inter: discord.Interaction):
            await inter.response.defer()
            await play_music(inter, self.results[int(sel.values[0])]['url'])
        sel.callback = callback
        v = discord.ui.View(); v.add_item(sel)
        await interaction.response.send_message("Konfirmasi pilihan:", view=v, ephemeral=True)

# --- 5. UI: DASHBOARD ---
class MusicDashboard(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.button(label="Pause/Resume", emoji="⏯️", style=discord.ButtonStyle.secondary)
    async def pp(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc:
            if vc.is_playing(): vc.pause()
            else: vc.resume()
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Loop", emoji="🔁", style=discord.ButtonStyle.gray)
    async def lp(self, interaction: discord.Interaction):
        q = get_queue(self.guild_id)
        q.loop = not q.loop
        button = [x for x in self.children if x.label == "Loop"][0]
        button.style = discord.ButtonStyle.success if q.loop else discord.ButtonStyle.gray
        await interaction.response.edit_message(view=self)

# --- 6. CORE LOGIC ---
async def play_music(interaction, url):
    q = get_queue(interaction.guild_id)
    # Pastikan bot masuk VC sebelum memutar
    if not interaction.guild.voice_client:
        if interaction.user.voice: await interaction.user.voice.channel.connect()
        else: return await interaction.channel.send("❌ Masuk VC dulu!")

    vc = interaction.guild.voice_client
    if vc.is_playing() or vc.is_paused():
        q.queue.append(url)
        return await interaction.followup.send("✅ Lagu ditambahkan ke antrean!", ephemeral=True)
    
    await start_stream(interaction, url)

async def start_stream(interaction, url):
    q = get_queue(interaction.guild_id)
    vc = interaction.guild.voice_client
    try:
        data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
        source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(data['url'], **FFMPEG_OPTIONS))
        q.current_info = {'title': data['title'], 'url': url, 'thumb': data.get('thumbnail')}
        vc.play(source, after=lambda e: bot.loop.create_task(next_logic(interaction)))
        
        if q.last_dashboard:
            try: await q.last_dashboard.delete()
            except: pass
        emb = discord.Embed(title="🎶 Now Playing", description=f"**{data['title']}**", color=0x5865F2)
        emb.set_thumbnail(url=data.get('thumbnail'))
        q.last_dashboard = await interaction.channel.send(embed=emb, view=MusicDashboard(interaction.guild_id))
    except Exception as e:
        await interaction.channel.send(f"❌ Eror saat memutar: {e}")

async def next_logic(interaction):
    q = get_queue(interaction.guild_id)
    vc = interaction.guild.voice_client
    if not vc: return
    if q.loop and q.current_info: await start_stream(interaction, q.current_info['url'])
    elif q.queue: await start_stream(interaction, q.queue.popleft())

# --- 7. COMMANDS ---
@bot.tree.command(name="loop", description="Aktifkan/Matikan pengulangan lagu")
async def loop_cmd(interaction: discord.Interaction):
    q = get_queue(interaction.guild_id)
    q.loop = not q.loop
    await interaction.response.send_message(f"🔁 Loop sekarang: {'AKTIF' if q.loop else 'MATI'}")

@bot.tree.command(name="play", description="Putar musik")
async def play(interaction: discord.Interaction, search: str):
    await interaction.response.defer()
    if "http" in search: await play_music(interaction, search)
    else:
        data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(f"ytsearch15:{search}", download=False))
        view = SearchView(data['entries'], interaction.user)
        await interaction.followup.send(embed=view.create_embed(), view=view)

@bot.tree.command(name="help", description="Bantuan")
async def help_cmd(interaction: discord.Interaction):
    emb = discord.Embed(title="💎 Help Menu", color=0x3498db)
    emb.add_field(name="Commands", value="`/play`, `/loop`, `/stop`, `/help`", inline=False)
    emb.set_footer(text=f"Dev: ikiiii | ID: 590774565115002880")
    await interaction.response.send_message(embed=emb)

bot.run(TOKEN)
        
