import nextcord
from nextcord.ext import commands
from nextcord import Interaction
from nextcord.ui import View, Button
import wavelink
import os
from flask import Flask
import threading

# ---------- Flask web server to satisfy Render ----------
app = Flask("")

@app.route("/")
def home():
    return "Yoruichi Bot is alive!"

def run():
    app.run(host="0.0.0.0", port=8080)

threading.Thread(target=run).start()

# ---------- Bot Setup ----------
intents = nextcord.Intents.all()
bot = commands.Bot(command_prefix="/", intents=intents)

OWNER_ID = 1355140133661184221  # Your owner ID
VC_CHANNEL_ID = None  # Will be set with /setchannel

LAVALINK_PASSWORD = os.environ.get("LAVALINK_PASSWORD", "youshallnotpass")
LAVALINK_HOST = os.environ.get("LAVALINK_HOST", "lavalink.dev")
LAVALINK_PORT = int(os.environ.get("LAVALINK_PORT", 2333))

# ---------- Auto-Responder ----------
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if "<@1284809746775408682>" in message.content:
        await message.channel.send(
            "😡 Don't try to flirt with him, he is my man 😘🥰"
        )
    await bot.process_commands(message)

# ---------- Lavalink ----------
@bot.event
async def on_ready():
    print(f"{bot.user} is online!")
    if not hasattr(bot, 'lavalink_node'):
        bot.lavalink_node = wavelink.Node(
            uri=f"http://{LAVALINK_HOST}:{LAVALINK_PORT}",
            password=LAVALINK_PASSWORD,
            identifier="MAIN"
        )
        await bot.lavalink_node.connect()

# ---------- Helper ----------
def is_owner(interaction: Interaction):
    return interaction.user.id == OWNER_ID

# ---------- Music Controls View ----------
class MusicControls(View):
    def __init__(self, player):
        super().__init__(timeout=None)  # persistent
        self.player = player

    @nextcord.ui.button(label="⏯️ Pause/Resume", style=nextcord.ButtonStyle.primary)
    async def pause_resume(self, button: Button, inter: Interaction):
        if self.player.is_paused():
            await self.player.resume()
            await inter.response.send_message("▶️ Resumed", ephemeral=True)
        else:
            await self.player.pause()
            await inter.response.send_message("⏸️ Paused", ephemeral=True)

    @nextcord.ui.button(label="⏭️ Skip", style=nextcord.ButtonStyle.secondary)
    async def skip(self, button: Button, inter: Interaction):
        await self.player.stop()
        await inter.response.send_message("⏭️ Skipped", ephemeral=True)

    @nextcord.ui.button(label="🔁 Loop", style=nextcord.ButtonStyle.success)
    async def loop(self, button: Button, inter: Interaction):
        self.player.loop = not getattr(self.player, 'loop', False)
        await inter.response.send_message(f"🔁 Loop is now {self.player.loop}", ephemeral=True)

# ---------- Slash Commands ----------
@bot.slash_command(description="Set VC for 24/7 music (Owner only)")
async def setchannel(interaction: Interaction, channel: nextcord.VoiceChannel):
    if not is_owner(interaction):
        await interaction.response.send_message("Only owner can use this!", ephemeral=True)
        return
    global VC_CHANNEL_ID
    VC_CHANNEL_ID = channel.id
    await interaction.response.send_message(f"Channel set to {channel.name} ✅")
    # Join VC immediately
    vc = bot.get_channel(VC_CHANNEL_ID)
    if vc:
        player = bot.lavalink_node.get_player(vc.guild.id)
        if not player:
            player: wavelink.Player = await vc.connect(cls=wavelink.Player)
        else:
            await player.connect(vc)

@bot.slash_command(description="Play a song from YouTube")
async def play(interaction: Interaction, query: str):
    if not VC_CHANNEL_ID:
        await interaction.response.send_message("VC not set. Use /setchannel first.", ephemeral=True)
        return
    vc = bot.get_channel(VC_CHANNEL_ID)
    player = bot.lavalink_node.get_player(vc.guild.id)
    track = await wavelink.YouTubeTrack.search(query, return_first=True)
    await player.play(track)

    # Embed with buttons
    embed = nextcord.Embed(title="Now Playing", description=f"{track.title} 🎵", color=0x00ff00)
    embed.set_footer(text=f"Requested by {interaction.user}")
    await interaction.response.send_message(embed=embed, view=MusicControls(player))

@bot.slash_command(description="Pause the current song")
async def pause(interaction: Interaction):
    vc = bot.get_channel(VC_CHANNEL_ID)
    player = bot.lavalink_node.get_player(vc.guild.id)
    await player.pause()
    await interaction.response.send_message("⏸️ Paused")

@bot.slash_command(description="Resume the song")
async def resume(interaction: Interaction):
    vc = bot.get_channel(VC_CHANNEL_ID)
    player = bot.lavalink_node.get_player(vc.guild.id)
    await player.resume()
    await interaction.response.send_message("▶️ Resumed")

@bot.slash_command(description="Skip the current song")
async def skip(interaction: Interaction):
    vc = bot.get_channel(VC_CHANNEL_ID)
    player = bot.lavalink_node.get_player(vc.guild.id)
    await player.stop()
    await interaction.response.send_message("⏭️ Skipped")

@bot.slash_command(description="View the queue")
async def queue(interaction: Interaction):
    vc = bot.get_channel(VC_CHANNEL_ID)
    player = bot.lavalink_node.get_player(vc.guild.id)
    q = player.queue
    if not q:
        await interaction.response.send_message("Queue is empty")
        return
    desc = "\n".join([f"{i+1}. {t.title}" for i, t in enumerate(q)])
    await interaction.response.send_message(f"**Queue:**\n{desc}")

@bot.slash_command(description="Clear the queue")
async def clearqueue(interaction: Interaction):
    vc = bot.get_channel(VC_CHANNEL_ID)
    player = bot.lavalink_node.get_player(vc.guild.id)
    player.queue.clear()
    await interaction.response.send_message("🗑️ Queue cleared")

@bot.slash_command(description="Loop the current song")
async def playloop(interaction: Interaction):
    vc = bot.get_channel(VC_CHANNEL_ID)
    player = bot.lavalink_node.get_player(vc.guild.id)
    player.loop = not getattr(player, 'loop', False)
    await interaction.response.send_message(f"🔁 Loop is now {player.loop}")

@bot.slash_command(description="Play FM stream")
async def fm(interaction: Interaction, url: str):
    vc = bot.get_channel(VC_CHANNEL_ID)
    player = bot.lavalink_node.get_player(vc.guild.id)
    track = wavelink.Track(uri=url, title="FM Stream")
    await player.play(track)
    await interaction.response.send_message(f"🎶 Playing FM stream: {url}")

# ---------- Run ----------
TOKEN = os.environ.get("DISCORD_TOKEN")
bot.run(TOKEN)
