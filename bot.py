import os
import nextcord
from nextcord.ext import commands
from nextcord import Interaction
import asyncio
import yt_dlp
from flask import Flask
import threading
import functools

# -------------------------
# FLASK KEEP-ALIVE SERVER
# -------------------------
app = Flask("")

@app.route("/")
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_flask, daemon=True).start()

# -------------------------
# DISCORD BOT SETUP
# -------------------------
intents = nextcord.Intents.all()
bot = commands.Bot(intents=intents)

ALLOWED_ROLE = 1436411629741801482

ytdl_opts = {
    "format": "bestaudio/best",
    "quiet": True,
    "noplaylist": True,
    "extractor_args": {"youtube": {"player_client": ["web"]}},
    "nocheckcertificate": True,
}
ytdl = yt_dlp.YoutubeDL(ytdl_opts)

ffmpeg_options = {
    "options": "-vn",
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
}

PLAYLIST = [
    "https://youtu.be/9dzub7uXWl4"
]

current_index = 0


def extract_info(url):
    info = ytdl.extract_info(url, download=False)
    return info["url"]


async def get_source_async(url):
    loop = asyncio.get_event_loop()
    audio_url = await loop.run_in_executor(None, functools.partial(extract_info, url))
    return nextcord.FFmpegPCMAudio(audio_url, **ffmpeg_options)


async def autoplay_loop(vc):
    global current_index
    
    await asyncio.sleep(2)

    while True:
        if not vc.is_connected():
            print("Voice client disconnected, stopping autoplay")
            break
        
        try:
            print(f"Fetching audio for: {PLAYLIST[current_index]}")
            source = await get_source_async(PLAYLIST[current_index])
            
            if not vc.is_connected():
                print("Disconnected while fetching, stopping")
                break
            
            vc.play(source)
            print("Playing:", PLAYLIST[current_index])

            while vc.is_playing() or vc.is_paused():
                await asyncio.sleep(1)
                if not vc.is_connected():
                    break

            current_index = (current_index + 1) % len(PLAYLIST)
            
        except Exception as e:
            print(f"Error playing audio: {e}")
            import traceback
            traceback.print_exc()
            await asyncio.sleep(5)


@bot.slash_command(
    name="join",
    description="Bot joins VC & plays music."
)
async def join(interaction: Interaction):

    await interaction.response.defer()

    roles = [r.id for r in interaction.user.roles]
    if ALLOWED_ROLE not in roles:
        return await interaction.followup.send("❌ You cannot use this command.", ephemeral=True)

    if interaction.user.voice is None:
        return await interaction.followup.send("❌ You must be in a voice channel.", ephemeral=True)

    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()

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


@bot.event
async def on_ready():
    print(f"Bot is ready! Logged in as {bot.user}")


bot.run(os.getenv("DISCORD_TOKEN"))
