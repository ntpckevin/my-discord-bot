import os
import asyncio
import time
import discord
from discord.ext import commands
import yt_dlp
from dotenv import load_dotenv
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# Keep-alive server to trick Render's port checker
class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_server():
    # Render automatically inputs a PORT environment variable, fallback to 8080 locally
    port = int(os.getenv("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), DummyServer)
    server.serve_forever()

# Start the web port in the background before the bot runs
threading.Thread(target=run_server, daemon=True).start()

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.moderation = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# ---------------------------------------------------------------------------
# INITIALIZATION & CUSTOM STATUS
# ---------------------------------------------------------------------------

@bot.event
async def on_ready():
    print(f'System Live: {bot.user.name} Security Layer Enabled.')
    
    # 1. Configures Custom Activity Text ("Watching over the server | !help")
    custom_activity = discord.Activity(type=discord.ActivityType.watching, name="over the server | !help")
    
    # 2. Applies the Activity along with a custom status (discord.Status.dnd, discord.Status.idle, discord.Status.online)
    await bot.change_presence(status=discord.Status.dnd, activity=custom_activity)
    print("Bot status has been locked to: Do Not Disturb (Watching...)")

# Dynamic commands allowing you to shift presence indicators on the fly
@bot.command(name='status_idle')
@commands.has_permissions(administrator=True)
async def status_idle(ctx):
    """Dynamically shifts the bot profile display state into yellow Idle indicators."""
    await bot.change_presence(status=discord.Status.idle, activity=bot.activity)
    await ctx.send("🌙 Status shifted to **Idle**.")

@bot.command(name='status_dnd')
@commands.has_permissions(administrator=True)
async def status_dnd(ctx):
    """Dynamically shifts the bot profile display state into red Do Not Disturb indicators."""
    await bot.change_presence(status=discord.Status.dnd, activity=bot.activity)
    await ctx.send("⛔ Status shifted to **Do Not Disturb**.")

# ---------------------------------------------------------------------------
# GLOBAL SECURITY CONFIGURATIONS (ANTI-SPAM & ANTI-NUKE)
# ---------------------------------------------------------------------------
SPAM_THRESHOLD = 5
SPAM_INTERVAL = 3.0
user_message_logs = {}

激NUKE_THRESHOLD = 3
NUKE_INTERVAL = 60.0
mod_action_logs = {}

YTDL_OPTIONS = {'format': 'bestaudio/best', 'noplaylist': True, 'quiet': True, 'default_search': 'ytsearch', 'source_address': '0.0.0.0'}
FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}
ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

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
            await message.author.timeout(duration, reason="Anti-Spam Triggered")
            await message.channel.purge(limit=5, check=lambda m: m.author.id == user_id)
            await message.channel.send(f"🛡️ {message.author.mention} has been muted for 5 minutes due to **Spam Detection**.")
            return
        except discord.Forbidden:
            pass
    await bot.process_commands(message)

async def check_nuke_activity(guild, mod_id, action_type):
    current_time = time.time()
    if mod_id not in mod_action_logs:
        mod_action_logs[mod_id] = {"channels": [], "roles": []}
    mod_action_logs[mod_id][action_type] = [t for t in mod_action_logs[mod_id][action_type] if current_time - t < NUKE_INTERVAL]
    mod_action_logs[mod_id][action_type].append(current_time)
    if len(mod_action_logs[mod_id][action_type]) >= NUKE_THRESHOLD:
        member = await guild.fetch_member(mod_id)
        if member and guild.me.top_role > member.top_role:
            await member.edit(roles=[], reason="Anti-Nuke Triggered")
            log_channel = guild.system_channel or discord.utils.get(guild.text_channels, name="mod-logs")
            if log_channel:
                await log_channel.send(f"🚨 **ANTI-NUKE ACTIVATED:** {member.mention} has had all permissions revoked.")

@bot.event
async def on_guild_channel_delete(channel):
    async for entry in channel.guild.audit_logs(action=discord.AuditLogAction.channel_delete, limit=1):
        if entry.user.id != bot.user.id:
            await check_nuke_activity(channel.guild, entry.user.id, "channels")

@bot.event
async def on_guild_role_delete(role):
    async for entry in role.guild.audit_logs(action=discord.AuditLogAction.role_delete, limit=1):
        if entry.user.id != bot.user.id:
            await check_nuke_activity(role.guild, entry.user.id, "roles")

# ---------------------------------------------------------------------------
# MODERATION SUITE
# ---------------------------------------------------------------------------
@bot.command(name='ban')
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason="No reason specified"):
    await member.ban(reason=reason)
    await ctx.send(f"🚨 **{member.display_name}** has been banned.")

@bot.command(name='kick')
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="No reason specified"):
    await member.kick(reason=reason)
    await ctx.send(f"✅ **{member.display_name}** has been kicked.")

# ---------------------------------------------------------------------------
# MUSIC STREAMING SYSTEMS
# ---------------------------------------------------------------------------
@bot.command(name='play')
async def play(ctx, *, search: str):
    if not ctx.author.voice:
        return await ctx.send("❌ You must be inside a Voice Channel.")
    if not ctx.voice_client:
        await ctx.author.voice.channel.connect()
    async with ctx.typing():
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(search, download=False))
        if 'entries' in data: data = data['entries'][0]
        url = data['url']
        player = discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS, before_options=FFMPEG_OPTIONS['before_options'])
        if ctx.voice_client.is_playing(): ctx.voice_client.stop()
        ctx.voice_client.play(player)
        await ctx.send(f"🎵 Now Playing: **{data['title']}**")

@bot.command(name='leave')
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("🔌 Disconnected.")

# ---------------------------------------------------------------------------
# WELCOME & GOODBYE
# ---------------------------------------------------------------------------
@bot.event
async def on_member_join(member):
    channel = member.guild.system_channel or discord.utils.get(member.guild.text_channels, name="welcome")
    if channel:
        await channel.send(f"👋 Welcome {member.mention} to the server!")

@bot.event
async def on_member_remove(member):
    channel = discord.utils.get(member.guild.text_channels, name="goodbye") or discord.utils.get(member.guild.text_channels, name="welcome")
    if channel:
        await channel.send(f"😢 **{member.name}** left the server.")

if __name__ == '__main__':
    bot.run(TOKEN)
