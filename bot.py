import os
import asyncio
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# 1. KEEP-ALIVE SERVER (TRICKS RENDER PORT CHECKS)
# ---------------------------------------------------------------------------
class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_server():
    port = int(os.getenv("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), DummyServer)
    server.serve_forever()

threading.Thread(target=run_server, daemon=True).start()

# ---------------------------------------------------------------------------
# 2. INITIALIZATION & SETUP
# ---------------------------------------------------------------------------
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.moderation = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

@bot.event
async def on_ready():
    print(f'System Live: {bot.user.name}')
    custom_activity = discord.Activity(type=discord.ActivityType.watching, name="over the server | /help")
    await bot.change_presence(status=discord.Status.dnd, activity=custom_activity)
    
    # Auto-Sync Slash Commands globally on start
    try:
        synced = await bot.tree.sync()
        print(f"Successfully synced {len(synced)} slash commands globally!")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

# 🚨 MANUAL SYNC RECOVERY CONFIGURATION
@bot.command(name='sync')
@commands.has_permissions(administrator=True)
async def sync(ctx):
    try:
        synced = await bot.tree.sync()
        await ctx.send(f"🔄 Success! Registered {len(synced)} Slash Commands. Type `/` to inspect!")
    except Exception as e:
        await ctx.send(f"❌ Sync failed: {e}")

# ---------------------------------------------------------------------------
# 3. MODERN MODERATION & TIMEOUT COMMAND SUITE (/)
# ---------------------------------------------------------------------------

@bot.tree.command(name="ban", description="Permanently bans a user from the server.")
@app_commands.checks.has_permissions(ban_members=True)
async def ban_slash(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason specified"):
    await member.ban(reason=reason)
    await interaction.response.send_message(f"🚨 **{member.display_name}** has been banned. Reason: {reason}")

@bot.tree.command(name="kick", description="Kicks a user out of the server.")
@app_commands.checks.has_permissions(kick_members=True)
async def kick_slash(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason specified"):
    await member.kick(reason=reason)
    await interaction.response.send_message(f"✅ **{member.display_name}** has been kicked. Reason: {reason}")

@bot.tree.command(name="timeout", description="Mutes a user's text and voice access temporarily.")
@app_commands.checks.has_permissions(moderate_members=True)
async def timeout_slash(interaction: discord.Interaction, member: discord.Member, minutes: int, reason: str = "No reason specified"):
    duration = asyncio.datetime.timedelta(minutes=minutes)
    await member.timeout(duration, reason=reason)
    await interaction.response.send_message(f"⏳ **{member.display_name}** has been timed out for {minutes} minutes. Reason: {reason}")

@bot.tree.command(name="untimeout", description="Removes a timeout constraint from a user.")
@app_commands.checks.has_permissions(moderate_members=True)
async def untimeout_slash(interaction: discord.Interaction, member: discord.Member):
    await member.timeout(None)
    await interaction.response.send_message(f"🔊 Restored text privileges to **{member.display_name}**.")

@bot.tree.command(name="warn", description="Issues a formal warning warning straight to a user's DMs.")
@app_commands.checks.has_permissions(manage_messages=True)
async def warn_slash(interaction: discord.Interaction, member: discord.Member, warning: str):
    try:
        await member.send(f"⚠️ **Warning from {interaction.guild.name}**: {warning}")
        await interaction.response.send_message(f"📥 Warning successfully issued to **{member.display_name}**.")
    except discord.Forbidden:
        await interaction.response.send_message(f"⚠️ Warned **{member.display_name}**, but their private DMs are locked.")

@bot.tree.command(name="purge", description="Mass-cleans chat history instantly.")
@app_commands.checks.has_permissions(manage_messages=True)
async def purge_slash(interaction: discord.Interaction, amount: int):
    if amount < 1:
        return await interaction.response.send_message("Specify a quantity greater than 0.", ephemeral=True)
    await interaction.response.defer(ephemeral=True) # Give bot extra time to execute clear
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"🗑️ Cleaned up **{len(deleted)}** messages.")

# ---------------------------------------------------------------------------
# 4. MUSIC STREAMING ENGINE (/)
# ---------------------------------------------------------------------------
YTDL_OPTIONS = {'format': 'bestaudio/best', 'noplaylist': True, 'quiet': True, 'default_search': 'ytsearch', 'source_address': '0.0.0.0'}
FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}
ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

@bot.tree.command(name="play", description="Streams high-quality audio from YouTube directly into voice channels.")
async def play_slash(interaction: discord.Interaction, search: str):
    if not interaction.user.voice:
        return await interaction.response.send_message("❌ You must join a Voice Channel first!", ephemeral=True)
    
    await interaction.response.defer() # Keep connection active while loading query elements
    
    if not interaction.guild.voice_client:
        await interaction.user.voice.channel.connect()

    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, lambda: ytdl.extract_info(search, download=False))
    if 'entries' in data: data = data['entries'][0]
    
    url = data['url']
    player = discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS, before_options=FFMPEG_OPTIONS['before_options'])
    
    if interaction.guild.voice_client.is_playing():
        interaction.guild.voice_client.stop()
        
    interaction.guild.voice_client.play(player)
    await interaction.followup.send(f"🎵 Now Streaming audio track: **{data['title']}**")

@bot.tree.command(name="leave", description="Stops audio playback and disconnects bot.")
async def leave_slash(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("🔌 Successfully disconnected from Voice Channel.")
    else:
        await interaction.response.send_message("❌ I'm not inside any voice connection hubs.", ephemeral=True)

# ---------------------------------------------------------------------------
# 5. GLOBAL UTILITY & MANAGEMENT (/)
# ---------------------------------------------------------------------------
@bot.tree.command(name="help", description="Displays the full command interface guide.")
async def help_slash(interaction: discord.Interaction):
    embed = discord.Embed(title="🤖 Server Assistant Handbook", color=discord.Color.blurple())
    embed.add_field(name="🛡️ Moderation Commands", value="`/ban`, `/kick`, `/timeout`, `/untimeout`, `/warn`, `/purge`", inline=False)
    embed.add_field(name="🎵 Music Streaming", value="`/play [search term]`, `/leave`", inline=False)
    embed.add_field(name="⚙️ Visual Customization", value="`/status_dnd`, `/status_idle`", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="status_idle", description="Toggles status dots to Idle.")
@app_commands.checks.has_permissions(administrator=True)
async def status_idle_slash(interaction: discord.Interaction):
    await bot.change_presence(status=discord.Status.idle, activity=bot.activity)
    await interaction.response.send_message("🌙 Status shifted to **Idle**.")

@bot.tree.command(name="status_dnd", description="Toggles status dots to Do Not Disturb.")
@app_commands.checks.has_permissions(administrator=True)
async def status_dnd_slash(interaction: discord.Interaction):
    await bot.change_presence(status=discord.Status.dnd, activity=bot.activity)
    await interaction.response.send_message("⛔ Status shifted to **Do Not Disturb**.")

# ---------------------------------------------------------------------------
# 6. AUTOMATED BACKGROUND SYSTEMS (ANTI-SPAM, ANTI-NUKE, GREETINGS)
# ---------------------------------------------------------------------------
SPAM_THRESHOLD = 5
SPAM_INTERVAL = 3.0
user_message_logs = {}

NUKE_THRESHOLD = 3
NUKE_INTERVAL = 60.0
mod_action_logs = {}

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return
    user_id = message.author.id
    current_time = time.time()
    if user_id not in user_message_logs:
        user_message_logs[user_id] = []
    user_message_logs[user_id] = [t for t in user_message_logs[user_id] if current_time - t < SPAM_INTERVAL]
    user_message_logs[user_id].append(current_time)
    if len(user_message_logs[user_id]) > SPAM_THRESHOLD:
        try:
            duration = asyncio.datetime.timedelta(minutes=5)
            await message.author.timeout(duration, reason="Anti-Spam Protection Triggered")
            await message.channel.purge(limit=5, check=lambda m: m.author.id == user_id)
            await message.channel.send(f"🛡️ {message.author.mention} has been auto-timed out for 5 minutes due to **Spam Detection**.")
            return
        except discord.Forbidden:
            pass
    await bot.process_commands(message)
