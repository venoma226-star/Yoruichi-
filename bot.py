import os
import nextcord
from nextcord.ext import commands
from nextcord import Interaction
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

ALLOWED_ROLE = 1436411629741801482

ytdl_opts = {
    "format": "bestaudio/best",
    "quiet": True,
    "noplaylist": True
}
ytdl = yt_dlp.YoutubeDL(ytdl_opts)

ffmpeg_options = {"options": "-vn"}

PLAYLIST = [
    "https://youtu.be/9dzub7uXWl4"
]

current_index = 0


def get_source(url):
    info = ytdl.extract_info(url, download=False)
    return nextcord.FFmpegPCMAudio(info["url"], **ffmpeg_options)


async def autoplay_loop(vc):
    global current_index

    while True:
        source = get_source(PLAYLIST[current_index])
        vc.play(source)
        print("Playing:", PLAYLIST[current_index])

        while vc.is_playing() or vc.is_paused():
            await asyncio.sleep(1)

        current_index = (current_index + 1) % len(PLAYLIST)


@bot.slash_command(
    name="join",
    description="Bot joins VC & plays music."
)
async def join(interaction: Interaction):

    # ✨ FIX: prevent timeout
    await interaction.response.defer()

    # Role check
    roles = [r.id for r in interaction.user.roles]
    if ALLOWED_ROLE not in roles:
        return await interaction.followup.send("❌ You cannot use this command.", ephemeral=True)

    if interaction.user.voice is None:
        return await interaction.followup.send("❌ You must be in a voice channel.", ephemeral=True)

    channel = interaction.user.voice.channel
    vc = await channel.connect()

    await interaction.followup.send(f"Joined **{channel}**. Starting music 🎶")

    bot.loop.create_task(autoplay_loop(vc))


@bot.slash_command(name="leave", description="Bot disconnects.")
async def leave(interaction: Interaction):

    await interaction.response.defer()

    roles = [r.id for r in interaction.user.roles]
    if ALLOWED_ROLE not in roles:
        return await interaction.followup.send("❌ No permission.", ephemeral=True)

    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.followup.send("Disconnected.")
    else:
        await interaction.followup.send("❌ Not in a VC.")


bot.run(os.getenv("DISCORD_TOKEN"))
