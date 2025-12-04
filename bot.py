import os
import nextcord
from nextcord.ext import commands
from nextcord import Interaction, SlashOption
import asyncio
import yt_dlp
from flask import Flask
import threading

# -------------------------
# FLASK KEEP-ALIVE SERVER
# -------------------------
app = Flask("")

@app.route("/")
def home():
    return "Bot is running!"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

threading.Thread(target=run_flask).start()

# -------------------------
# DISCORD BOT SETUP
# -------------------------
intents = nextcord.Intents.all()
bot = commands.Bot(intents=intents)

GUILD_ID = None  # Auto-global slash cmd – works everywhere
ALLOWED_ROLE = 1436411629741801482  # your role ID

ytdl_opts = {
    "format": "bestaudio/best",
    "quiet": True,
    "noplaylist": True
}
ytdl = yt_dlp.YoutubeDL(ytdl_opts)

ffmpeg_options = {"options": "-vn"}

# -------------------------
# PLAYLIST WITH YOUR SONG
# -------------------------
PLAYLIST = [
    "https://youtu.be/9dzub7uXWl4"
]

current_index = 0


# -------------------------
# GET AUDIO SOURCE
# -------------------------
def get_source(url):
    info = ytdl.extract_info(url, download=False)
    return nextcord.FFmpegPCMAudio(info["url"], **ffmpeg_options)


# -------------------------
# AUTO-LOOP PLAYER
# -------------------------
async def autoplay_loop(vc):
    global current_index

    while True:
        source = get_source(PLAYLIST[current_index])
        vc.play(source)

        while vc.is_playing() or vc.is_paused():
            await asyncio.sleep(1)

        current_index = (current_index + 1) % len(PLAYLIST)


# -------------------------
# SLASH COMMAND: JOIN
# -------------------------
@bot.slash_command(
    name="join",
    description="Bot joins VC & starts auto music loop."
)
async def join(interaction: Interaction):

    # Check role
    roles = [r.id for r in interaction.user.roles]
    if ALLOWED_ROLE not in roles:
        return await interaction.response.send_message(
            "❌ You do not have permission to use this command.",
            ephemeral=True
        )

    # Must be in VC
    if interaction.user.voice is None:
        return await interaction.response.send_message(
            "❌ You must be in a voice channel.",
            ephemeral=True
        )

    channel = interaction.user.voice.channel
    vc = await channel.connect()

    await interaction.response.send_message(
        f"Joined **{channel}**. Starting music loop 🎵"
    )

    bot.loop.create_task(autoplay_loop(vc))


# -------------------------
# SLASH COMMAND: LEAVE
# -------------------------
@bot.slash_command(
    name="leave",
    description="Bot disconnects from VC."
)
async def leave(interaction: Interaction):

    # Role check
    roles = [r.id for r in interaction.user.roles]
    if ALLOWED_ROLE not in roles:
        return await interaction.response.send_message(
            "❌ You cannot use this command.",
            ephemeral=True
        )

    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("Disconnected.")
    else:
        await interaction.response.send_message("❌ Bot is not in a VC.")


# -------------------------
# RUN BOT
# -------------------------
bot.run(os.getenv("DISCORD_TOKEN"))
