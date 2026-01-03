
import datetime
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


# 1. SETUP YT-DLP (DIPERBAIKI UNTUK SUARA JERNIH)
YTDL_OPTIONS = {
    'format': 'bestaudio/best', 
    'noplaylist': True,
    'default_search': 'ytsearch10',
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'source_address': '0.0.0.0',
    'cookiefile': COOKIES_FILE if os.path.exists(COOKIES_FILE) else None,
}

# --- INI BARIS YANG TADI HILANG ---
ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)
# ---------------------------------

# 2. SETUP FFMPEG (DIPERBAIKI AGAR TIDAK KUSUT/STUTTER)
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -filter:a "volume=0.5" -b:a 320k' 
}





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
        
        # Posisi Logo Loading dipindah ke kanan atas agar rapi
        embed.set_thumbnail(url="https://i.ibb.co.com/KppFQ6N6/Logo1.gif")
        
        # Field dibuat sejajar (Inline) agar teks rapi ke samping
        embed.add_field(name="🛰️ Server Cluster", value="`Jakarta-ID`", inline=True)
        embed.add_field(name="⚡ Latency", value=f"`{round(bot.latency * 1000)}ms`", inline=True)
        embed.add_field(name="📡 Status", value="`Connected`", inline=True)
        
        embed.add_field(name="💡 Guide", value="Ketik `/help` untuk panduan", inline=False)
        
        # Waktu update tetap simpel
        waktu_sekarang = datetime.datetime.now().strftime('%d/%m/%Y %H:%M')
        embed.add_field(name="📅 Terakhir Diupdate", value=f"`{waktu_sekarang} WIB`", inline=False)

        embed.set_footer(
            text="System Online • ikiii angels Project v17", 
            icon_url=bot.user.avatar.url if bot.user.avatar else None
        )
        
        # Gambar di bawah bisa kamu isi banner server atau dikosongkan (set_image)
        embed.set_image(url="https://i.getpantry.cloud/apf/help_banner.gif") 
        
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
            
            
            # --- LOGIKA AUTO-DISCONNECT (DENGAN PEMBATALAN) ---
            if msg_chan:
                # Kita simpan ke variabel 'peringatan' agar bisa dihapus jika batal
                peringatan = await msg_chan.send("⚠️ **Informasi:** Tidak ada pengguna di Voice Channel. Bot akan otomatis keluar dalam **30 detik**.", delete_after=30)
            
            # Tunggu selama 30 detik
            await asyncio.sleep(30) 
            
            # Cek lagi kondisi Voice Client terbaru setelah 30 detik
            vc_sekarang = member.guild.voice_client
            
            if vc_sekarang and vc_sekarang.channel:
                # Jika ada user masuk (jumlah member > 1, termasuk bot)
                if len(vc_sekarang.channel.members) > 1:
                    try: 
                        await peringatan.delete() # Hapus pesan peringatan "akan keluar"
                    except: 
                        pass
                    
                    # Pesan konfirmasi pembatalan sesuai permintaanmu
                    await msg_chan.send("✅ **Informasi:** Ada user yang masuk, bot akan membatalkan keluar otomatis. ✨", delete_after=15)
                
                # Jika masih sendirian (hanya bot)
                else:
                    q = get_queue(member.guild.id)
                    q.queue.clear() # Bersihkan antrean
                    await vc_sekarang.disconnect() # Cabut dari voice
                    await msg_chan.send("👋 **Informasi:** Bot telah keluar karena tidak ada aktivitas di Voice Channel.", delete_after=10)




class SearchControlView(discord.ui.View):
    def __init__(self, entries, user, page=0):
        super().__init__(timeout=60)
        self.entries = entries
        self.user = user
        self.page = page
        self.per_page = 5
        self.update_view()

    def update_view(self):
        self.clear_items()
        
        start = self.page * self.per_page
        end = start + self.per_page
        current_batch = self.entries[start:end]

        options = []
        for i, entry in enumerate(current_batch):
            real_idx = start + i + 1
            options.append(discord.SelectOption(
                label=f"Nomor {real_idx}", 
                value=entry['webpage_url'], 
                description=entry['title'][:50],
                emoji="🎶"
            ))
            
        select = discord.ui.Select(
            placeholder=f"🎯 Pilih Lagu Halaman {self.page + 1}...", 
            options=options
        )
        
        async def select_callback(interaction: discord.Interaction):
            if interaction.user != self.user:
                return await interaction.response.send_message("❌ Ini bukan menu kamu!", ephemeral=True)
            
            await interaction.response.defer()
            await play_music(interaction, select.values[0])
            
            try:
                await interaction.delete_original_response()
            except:
                pass

        select.callback = select_callback
        # --- BARIS PENTING DI BAWAH INI TADI HILANG ---
        self.add_item(select) 
        # ---------------------------------------------

        if self.page > 0:
            btn_prev = discord.ui.Button(label="Halaman 1", emoji="⬅️", style=discord.ButtonStyle.gray)
            async def prev_callback(interaction: discord.Interaction):
                if interaction.user != self.user: return
                self.page = 0
                self.update_view()
                await interaction.response.edit_message(embed=self.create_embed(), view=self)
            btn_prev.callback = prev_callback
            self.add_item(btn_prev)

        if self.page == 0 and len(self.entries) > 5:
            btn_next = discord.ui.Button(label="Halaman 2", emoji="➡️", style=discord.ButtonStyle.gray)
            async def next_callback(interaction: discord.Interaction):
                if interaction.user != self.user: return
                self.page = 1
                self.update_view()
                await interaction.response.edit_message(embed=self.create_embed(), view=self)
            btn_next.callback = next_callback
            self.add_item(btn_next)

        btn_cancel = discord.ui.Button(label="Batalkan", emoji="✖️", style=discord.ButtonStyle.danger)
        async def cancel_callback(interaction: discord.Interaction):
            if interaction.user == self.user:
                try: await interaction.message.delete()
                except: pass
        btn_cancel.callback = cancel_callback
        self.add_item(btn_cancel)

    def create_embed(self):
        start = self.page * self.per_page
        end = start + self.per_page
        current_songs = self.entries[start:end]
        
        description = "✨ **Silakan pilih lagu yang ingin diputar:**\n\n"
        for i, entry in enumerate(current_songs):
            real_idx = start + i + 1
            description += f"✨ `{real_idx}.` {entry['title'][:60]}...\n"
            
        embed = discord.Embed(title="🔍 Hasil Pencarian Musik", description=description, color=0xf1c40f)
        embed.set_footer(text=f"Halaman {self.page + 1} dari 2 • Gunakan menu dropdown di bawah", icon_url=self.user.display_avatar.url)
        return embed




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
            return await interaction.response.send_message("📪 Antrean kosong.", ephemeral=True, delete_after=20)
        
        emb = discord.Embed(title="📜 Antrean Musik Saat Ini", color=0x2b2d31)
        description = ""
        options = []
        for i, item in enumerate(list(q.queue)[:10]):
            description += f"**{i+1}.** {item['title'][:50]}...\n"
            options.append(discord.SelectOption(label=f"{i+1}. {item['title'][:25]}", value=str(i)))
        
        emb.description = description
        select = discord.ui.Select(placeholder="🎯 Pilih lagu untuk dilompati...", options=options)
        
        async def select_callback(inter: discord.Interaction):
            idx = int(select.values[0])
            chosen = q.queue[idx]
            del q.queue[idx]
            q.queue.appendleft(chosen)
            if inter.guild.voice_client:
                inter.guild.voice_client.stop()
            await inter.response.send_message(f"🚀 Memutar: **{chosen['title']}**", ephemeral=True, delete_after=5)
            
        select.callback = select_callback
        view = discord.ui.View()
        view.add_item(select)
        await interaction.response.send_message(embed=emb, view=view, ephemeral=True)

    @discord.ui.button(label="Skip", emoji="⏭️", style=discord.ButtonStyle.primary)
    async def sk(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 1. Defer dulu agar tidak "Interaction Failed" (memberi waktu bot berpikir)
        await interaction.response.defer(ephemeral=False)
        
        q = get_queue(self.guild_id)
        vc = interaction.guild.voice_client
        
        if not vc or not (vc.is_playing() or vc.is_paused()):
            return await interaction.followup.send("❌ **Informasi:** Tidak ada lagu untuk di-skip.", ephemeral=True)

        # 2. Ambil Judul Lagu saat ini
        current_title = "Tidak diketahui"
        if q.last_dashboard and q.last_dashboard.embeds:
            try:
                full_desc = q.last_dashboard.embeds[0].description
                if "[" in full_desc and "]" in full_desc:
                    current_title = full_desc.split('[')[1].split(']')[0]
            except:
                pass

        # 3. Cek Antrean Berikutnya
        next_info = "Antrean habis, bot akan standby. ✨"
        if q.queue:
            next_info = f"⏭️ **Selanjutnya:** {q.queue[0]['title']}"

        embed = discord.Embed(
            title="⏭️ MUSIC SKIP SYSTEM",
            description=(
                f"✨ **{interaction.user.mention}** telah melewati lagu!\n\n"
                f"🗑️ **Dilewati:** {current_title}\n"
                f"📥 **Status Antrean:** {next_info}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=0xe74c3c
        )
        embed.set_footer(text="Gunakan /play untuk menambah lagu", icon_url=interaction.user.display_avatar.url)

        # 4. Eksekusi Stop & Kirim Pesan
        vc.stop()
        await interaction.followup.send(embed=embed)
        # Hapus pesan otomatis setelah 15 detik (manual karena followup tidak support delete_after)
        await asyncio.sleep(15)
        try:
            await (await interaction.original_response()).delete()
        except:
            pass

    @discord.ui.button(label="Stop", emoji="⏹️", style=discord.ButtonStyle.danger)
    async def st(self, interaction: discord.Interaction, button: discord.ui.Button):
        q = get_queue(self.guild_id)
        vc = interaction.guild.voice_client
        jumlah_antrean = len(q.queue)
        
        q.queue.clear()
        if vc:
            await vc.disconnect()
            
        embed = discord.Embed(
            title="🛑 SYSTEM TERMINATED",
            description=(
                f"✨ **{interaction.user.mention}** telah mematikan pemutar musik.\n\n"
                f"🧹 **Pembersihan:** `{jumlah_antrean}` lagu telah dihapus dari antrean.\n"
                f"📡 **Status:** Bot telah keluar dari Voice Channel.\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=0x2f3136
        )
        embed.set_thumbnail(url="https://i.ibb.co.com/KppFQ6N6/Logo1.gif")
        
        await interaction.response.send_message(embed=embed, delete_after=20)



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
    q = get_queue(interaction.guild_id)
    vc = interaction.guild.voice_client
    if not vc: return
    
    try:
        # Stop jika masih ada lagu sisa
        if vc.is_playing() or vc.is_paused():
            vc.stop()
        
        # Jeda sebentar agar FFmpeg lama mati total
        await asyncio.sleep(0.5)

        # Ambil info lagu (Penting: handle jika url ternyata hasil search)
        data = await asyncio.get_event_loop().run_in_executor(
            None, lambda: ytdl.extract_info(url, download=False)
        )
        
        # Jika data adalah playlist hasil search, ambil index pertama
        if 'entries' in data:
            data = data['entries'][0]

        # Inisialisasi Audio
        audio_source = discord.FFmpegPCMAudio(data['url'], **FFMPEG_OPTIONS)
        source = discord.PCMVolumeTransformer(audio_source, volume=q.volume) 
        
        def after_playing(error):
            if error: print(f"Player error: {error}")
            # Panggil antrean berikutnya
            asyncio.run_coroutine_threadsafe(next_logic(interaction), bot.loop)
            
        vc.play(source, after=after_playing)
        
        # Bersihkan dashboard lama
        if q.last_dashboard:
            try: await q.last_dashboard.delete()
            except: pass
            
        emb = discord.Embed(
            title="🎶 Sedang Diputar", 
            description=f"**[{data['title']}]({data.get('webpage_url', url)})**", 
            color=0x2ecc71
        )
        emb.set_thumbnail(url=data.get('thumbnail'))
        emb.set_footer(text=f"Permintaan: {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        
        q.last_dashboard = await interaction.channel.send(embed=emb, view=MusicDashboard(interaction.guild_id))
        
    except Exception as e:
        print(f"Error pada start_stream: {e}")
        # Jika gagal, jangan biarkan bot macet, paksa pindah lagu berikutnya
        asyncio.run_coroutine_threadsafe(next_logic(interaction), bot.loop)



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



# --- 8. COMMANDS (UPDATE PADA BAGIAN PLAY) ---
@bot.tree.command(name="play", description="Putar musik")
async def play(interaction: discord.Interaction, cari: str):
    await interaction.response.defer()
    if not interaction.user.voice: 
        return await interaction.followup.send("❌ Masuk Voice dulu!", ephemeral=True)
    
    if "http" in cari: 
        await play_music(interaction, cari)
        await interaction.followup.send("✅ Permintaan diproses!", ephemeral=True)
    else:
        # Mencari 15 lagu (3 halaman x 5 lagu) agar pencarian cepat
        data = await asyncio.get_event_loop().run_in_executor(
            None, lambda: ytdl.extract_info(f"ytsearch15:{cari}", download=False)
        )
        
        if not data['entries']: 
            return await interaction.followup.send("❌ Tidak ketemu.", ephemeral=True)
            
        # Memanggil View yang sudah diperbaiki
        view = SearchControlView(data['entries'], interaction.user)
        await interaction.followup.send(embed=view.create_embed(), view=view)
        


@bot.tree.command(name="stop", description="Mematikan musik dan mengeluarkan bot dari voice channel")
async def stop_cmd(interaction: discord.Interaction):
    q = get_queue(interaction.guild_id)
    vc = interaction.guild.voice_client
    
    # Ambil data jumlah antrean sebelum dihapus
    jumlah_antrean = len(q.queue)
    
    if vc:
        # Logika pembersihan
        q.queue.clear()
        await vc.disconnect()
        
        # Buat Embed yang sinkron dengan tombol dashboard
        embed = discord.Embed(
            title="🛑 COMMAND STOP EXECUTED",
            description=(
                f"✨ **{interaction.user.mention}** telah menghentikan seluruh sesi musik.\n\n"
                f"🧹 **Pembersihan:** `{jumlah_antrean}` lagu di antrean telah dibersihkan.\n"
                f"📡 **Status:** Koneksi Voice Channel diputuskan.\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=0x2f3136 # Warna gelap profesional
        )
        embed.set_thumbnail(url="https://i.ibb.co.com/KppFQ6N6/Logo1.gif")
        embed.set_footer(text="Sesi berakhir via Slash Command", icon_url=bot.user.avatar.url)

        # Kirim ke publik agar semua tahu siapa yang mematikan musik
        await interaction.response.send_message(embed=embed, delete_after=20)
    else:
        # Jika bot tidak ada di voice channel
        await interaction.response.send_message("❌ **Gagal:** Bot tidak sedang berada di Voice Channel.", ephemeral=True)


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

@bot.tree.command(name="skip", description="Lewati lagu yang sedang berjalan")
async def skip_cmd(interaction: discord.Interaction):
    # 1. Defer agar tidak "Interaction Failed"
    await interaction.response.defer(ephemeral=False)
    
    q = get_queue(interaction.guild_id)
    vc = interaction.guild.voice_client
    
    if vc and (vc.is_playing() or vc.is_paused()):
        # 2. Ambil Judul Lagu (Logika yang lebih aman)
        current_title = "Tidak diketahui"
        if q.last_dashboard and q.last_dashboard.embeds:
            try:
                full_desc = q.last_dashboard.embeds[0].description
                if "[" in full_desc and "]" in full_desc:
                    current_title = full_desc.split('[')[1].split(']')[0]
            except:
                pass

        # 3. Cek Antrean Berikutnya
        next_info = "Antrean kosong, bot akan standby. ✨"
        if q.queue:
            next_info = f"⏭️ **Selanjutnya:** {q.queue[0]['title']}"

        # 4. Buat Embed yang Elegan
        embed = discord.Embed(
            title="⏭️ COMMAND SKIP EXECUTED",
            description=(
                f"✨ **{interaction.user.mention}** meminta skip lagu!\n\n"
                f"🗑️ **Dilewati:** {current_title}\n"
                f"📥 **Status:** {next_info}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=0xe67e22 # Warna orange keren
        )
        embed.set_footer(text="System Skip Otomatis", icon_url=bot.user.avatar.url if bot.user.avatar else None)

        # 5. Eksekusi
        vc.stop()
        
        # Kirim menggunakan followup karena sudah di-defer
        await interaction.followup.send(embed=embed)
        
        # Hapus pesan otomatis setelah 15 detik
        await asyncio.sleep(15)
        try:
            msg = await interaction.original_response()
            await msg.delete()
        except:
            pass
    else:
        # Jika tidak ada lagu, kirim pesan error (lewat followup karena sudah defer)
        await interaction.followup.send("❌ **Gagal:** Bot tidak sedang memutar musik.", ephemeral=True)


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
