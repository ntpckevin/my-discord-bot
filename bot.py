import os
import asyncio
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import discord
from discord import app_commands # New system wrapper
from discord.ext import commands
import yt_dlp
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# KEEP-ALIVE SERVER (TRICKS RENDER FOR FREE 24/7 HOSTING)
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
# INITIALIZATION & CUSTOM STATUS
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
    
    # Pre-sync slash commands globally across all servers on startup
    try:
        synced = await bot.tree.sync()
        print(f"Successfully synced {len(synced)} slash commands globally!")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

# 🚨 THE SECRET SYNC COMMAND
# Type '!sync' in your server once to force Discord to update your '/' menu immediately!
@bot.command(name='sync')
@commands.has_permissions(administrator=True)
async def sync(ctx):
    try:
        synced = await bot.tree.sync()
        await ctx.send(f"🔄 Success! Registered {len(synced)} Slash Commands. Check your `/` menu now!")
    except Exception as e:
        await ctx.send(f"❌ Sync failed: {e}")

# ---------------------------------------------------------------------------
# NEW MODERN SLASH COMMANDS (/)
# ---------------------------------------------------------------------------

@bot.tree.command(name="help", description="Displays the server assistant help guide.")
async def help_slash(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🤖 Server Assistant Multi-Tool",
        description="Use your slash actions to interact with moderation, security, and music properties!",
        color=discord.Color.blurple()
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="status_idle", description="Shifts the bot status indicator to Idle.")
@app_commands.checks.has_permissions(administrator=True)
async def status_idle_slash(interaction: discord.Interaction):
    await bot.change_presence(status=discord.Status.idle, activity=bot.activity)
    await interaction.response.send_message("🌙 Status shifted to **Idle**.")

@bot.tree.command(name="status_dnd", description="Shifts the bot status indicator to Do Not Disturb.")
@app_commands.checks.has_permissions(administrator=True)
async def status_dnd_slash(interaction: discord.Interaction):
    await bot.change_presence(status=discord.Status.dnd, activity=bot.activity)
    await interaction.response.send_message("⛔ Status shifted to **Do Not Disturb**.")

@bot.tree.command(name="ban", description="Bans a user from the server.")
@app_commands.checks.has_permissions(ban_members=True)
async def ban_slash(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason specified"):
    await member.ban(reason=reason)
    await interaction.response.send_message(f"🚨 **{member.display_name}** has been banned. Reason: {reason}")

@bot.tree.command(name="kick", description="Kicks a user from the server.")
@app_commands.checks.has_permissions(kick_members=True)
async def kick_slash(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason specified"):
    await member.kick(reason=reason)
    await interaction.response.send_message(f"✅ **{member.display_name}** has been kicked. Reason: {reason}")

# ---------------------------------------------------------------------------
# GLOBAL SECURITY CONFIGURATIONS (ANTI-SPAM & ANTI-NUKE)
# ---------------------------------------------------------------------------
SPAM_THRESHOLD = 5
SPAM_INTERVAL = 3.0
user_message_logs = {}

NUKE_THRESHOLD = 3
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

# ... (Keep your old on_guild_channel_delete, on_guild_role_delete, and member join/leave events exactly the same at the bottom) ...

if __name__ == '__main__':
    bot.run(TOKEN)
