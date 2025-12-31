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
    'nocheckcertificate': True,
    'cookiefile': COOKIES_FILE if os.path.exists(COOKIES_FILE) else None,
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

# --- 2. SETUP BOT CLASS ---
class ModernBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Ini akan mendaftarkan semua /command agar muncul di Discord
        await self.tree.sync()
        print("✅ Slash Commands Synchronized!")

    async def on_ready(self):
        print(f"🤖 {self.user} is online!")

bot = ModernBot()

# --- 3. STORAGE & QUEUE SYSTEM ---
queues = {}

class MusicQueue:
    def __init__(self):
        self.queue = deque()
        self.current_track = None
        self.loop = False

def get_queue(guild_id):
    if guild_id not in queues:
        queues[guild_id] = MusicQueue()
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
        embed = discord.Embed(title="🔍 Music Search Results", color=0x2b2d31)
        for i, res in enumerate(current_list):
            dur = f"{res.get('duration')//60}:{res.get('duration')%60:02d}"
            embed.add_field(
                name=f"{start+i+1}. {res['title'][:60]}", 
                value=f"👤 {res['uploader']} | 🕒 {dur}", 
                inline=False
            )
        embed.set_footer(text=f"Page {self.page+1}/3 • Requested by {self.user.display_name}")
        return embed

    @discord.ui.button(label="⬅️ Previous", style=discord.ButtonStyle.gray)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
            await interaction.response.edit_message(embed=self.create_embed())

    @discord.ui.button(label="Next ➡️", style=discord.ButtonStyle.gray)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page < 2:
            self.page += 1
            await interaction.response.edit_message(embed=self.create_embed())

    @discord.ui.button(label="Select Song", style=discord.ButtonStyle.green)
    async def select(self, interaction: discord.Interaction, button: discord.ui.Button):
        options = [discord.SelectOption(label=f"Song {i+1}", value=str(i)) for i in range(self.page*5, (self.page*5)+5)]
        sel = discord.ui.Select(placeholder="Choose song number...", options=options)
        
        async def callback(inter: discord.Interaction):
            await inter.response.defer()
            await start_playing(inter, self.results[int(sel.values[0])]['url'])
        
        sel.callback = callback
        view = discord.ui.View(); view.add_item(sel)
        await interaction.response.send_message("Select a number from this page:", view=view, ephemeral=True)

# --- 5. UI: DYNAMIC DASHBOARD ---
class MusicDashboard(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.button(label="Pause", emoji="⏸️", style=discord.ButtonStyle.secondary)
    async def pp(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if not vc: return
        if vc.is_playing():
            vc.pause()
            button.label, button.emoji, button.style = "Resume", "▶️", discord.ButtonStyle.success
        else:
            vc.resume()
            button.label, button.emoji, button.style = "Pause", "⏸️", discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Volume", emoji="🔊", style=discord.ButtonStyle.gray)
    async def vol(self, interaction: discord.Interaction, button: discord.ui.Button):
        v = discord.ui.View()
        def make_btn(l, val):
            b = discord.ui.Button(label=l)
            async def c(i: discord.Interaction):
                if i.guild.voice_client and i.guild.voice_client.source:
                    i.guild.voice_client.source.volume = val
                    await i.response.send_message(f"🔊 Volume set to {int(val*100)}%", ephemeral=True)
            b.callback = c; return b
        v.add_item(make_btn("20%", 0.2)); v.add_item(make_btn("50%", 0.5)); v.add_item(make_btn("100%", 1.0))
        await interaction.response.send_message("Select volume level:", view=v, ephemeral=True)

    @discord.ui.button(label="Skip", emoji="⏭️", style=discord.ButtonStyle.primary)
    async def sk(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild.voice_client:
            interaction.guild.voice_client.stop()
            await interaction.response.send_message("⏭️ Skipped!", ephemeral=True)

    @discord.ui.button(label="Loop", emoji="🔁", style=discord.ButtonStyle.gray)
    async def lp(self, interaction: discord.Interaction, button: discord.ui.Button):
        q = get_queue(self.guild_id)
        q.loop = not q.loop
        button.style = discord.ButtonStyle.success if q.loop else discord.ButtonStyle.gray
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Stop", emoji="🛑", style=discord.ButtonStyle.danger)
    async def st(self, interaction: discord.Interaction, button: discord.ui.Button):
        get_queue(self.guild_id).queue.clear()
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("🛑 Disconnected.", ephemeral=True)

# --- 6. CORE MUSIC LOGIC ---
async def start_playing(interaction, url):
    vc = interaction.guild.voice_client
    q = get_queue(interaction.guild_id)
    
    try:
        data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
    except Exception as e:
        return await interaction.followup.send(f"❌ YouTube Error: {e}\n(Make sure you uploaded `youtube_cookies.txt`)")

    source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(data['url'], **FFMPEG_OPTIONS))
    track = {'source': source, 'title': data['title'], 'url': url, 'thumb': data.get('thumbnail')}

    if vc.is_playing() or vc.is_paused():
        q.queue.append(track)
        await interaction.followup.send(f"✅ Added to queue: **{track['title']}**")
    else:
        q.current_track = track
        vc.play(source, after=lambda e: bot.loop.create_task(play_next(interaction)))
        emb = discord.Embed(title="🎶 Now Playing", description=f"[{track['title']}]({track['url']})", color=0x5865F2)
        emb.set_thumbnail(url=track['thumb'])
        await interaction.followup.send(embed=emb, view=MusicDashboard(interaction.guild_id))

async def play_next(interaction):
    q = get_queue(interaction.guild_id)
    vc = interaction.guild.voice_client
    if not vc: return

    if not q.loop and q.queue:
        q.current_track = q.queue.popleft()
    elif not q.loop and not q.queue:
        q.current_track = None
        return

    # Jika loop aktif, q.current_track tetap sama
    data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(q.current_track['url'], download=False))
    new_source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(data['url'], **FFMPEG_OPTIONS))
    
    vc.play(new_source, after=lambda e: bot.loop.create_task(play_next(interaction)))
    
    emb = discord.Embed(title="🎶 Next Track", description=f"[{q.current_track['title']}]({q.current_track['url']})", color=0x5865F2)
    emb.set_thumbnail(url=q.current_track['thumb'])
    await interaction.channel.send(embed=emb, view=MusicDashboard(interaction.guild_id))

# --- 7. SLASH COMMANDS ---
@bot.tree.command(name="play", description="Search or Play a song")
async def play(interaction: discord.Interaction, pencarian: str):
    await interaction.response.defer()
    if not interaction.user.voice:
        return await interaction.followup.send("❌ Join a Voice Channel first!")
    
    if not interaction.guild.voice_client:
        await interaction.user.voice.channel.connect()

    if "http" in pencarian:
        await start_playing(interaction, pencarian)
    else:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(f"ytsearch15:{pencarian}", download=False))
        view = SearchView(data['entries'], interaction.user)
        await interaction.followup.send(embed=view.create_embed(), view=view)

@bot.tree.command(name="masuk", description="Bot joins VC")
async def masuk(interaction: discord.Interaction):
    if interaction.user.voice:
        await interaction.user.voice.channel.connect()
        await interaction.response.send_message("📥 Connected!")
    else:
        await interaction.response.send_message("❌ Join a VC first!")

@bot.tree.command(name="keluar", description="Bot leaves VC")
async def keluar(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("📤 Disconnected!")

@bot.tree.command(name="pause", description="Pause music")
async def pause(interaction: discord.Interaction):
    if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
        interaction.guild.voice_client.pause()
        await interaction.response.send_message("⏸️ Paused.")

@bot.tree.command(name="resume", description="Resume music")
async def resume(interaction: discord.Interaction):
    if interaction.guild.voice_client and interaction.guild.voice_client.is_paused():
        interaction.guild.voice_client.resume()
        await interaction.response.send_message("▶️ Resumed.")

bot.run(TOKEN)
