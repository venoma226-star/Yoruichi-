import nextcord
from nextcord.ext import commands
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

# Start Flask server
threading.Thread(target=run_flask).start()

# -------------------------
# DISCORD BOT SETUP
# -------------------------
intents = nextcord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

ytdl_opts = {
    "format": "bestaudio/best",
    "quiet": True,
    "noplaylist": True
}
ytdl = yt_dlp.YoutubeDL(ytdl_opts)

ffmpeg_options = {
    "options": "-vn"
}

# -------------------------
# PLAYLIST WITH YOUR SONG
# -------------------------
PLAYLIST = [
    "https://youtu.be/9dzub7uXWl4"
]

current_index = 0
voice_client = None


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

        # Wait until track finishes
        while vc.is_playing() or vc.is_paused():
            await asyncio.sleep(1)

        current_index = (current_index + 1) % len(PLAYLIST)


# -------------------------
# JOIN COMMAND
# -------------------------
@bot.command()
async def join(ctx):
    global voice_client

    if ctx.author.voice is None:
        return await ctx.send("You must be in a voice channel.")

    channel = ctx.author.voice.channel
    voice_client = await channel.connect()
    await ctx.send(f"Joined **{channel}**. Starting auto music loop 🎵")

    bot.loop.create_task(autoplay_loop(voice_client))


# -------------------------
# LEAVE COMMAND
# -------------------------
@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("Disconnected.")
    else:
        await ctx.send("Not in a voice channel.")
        
# -------------------------
# RUN BOT
# -------------------------
import os
bot.run(os.getenv("DISCORD_TOKEN"))
