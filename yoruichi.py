import os
import threading
import nextcord
from nextcord.ext import commands
from nextcord import Interaction
from flask import Flask
import asyncio

# ---------- FLASK KEEP-ALIVE ----------
app = Flask("")

@app.route("/")
def home():
    return "Bot is alive!"

def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

threading.Thread(target=run_flask).start()

# ---------- ENV ----------
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# ---------- BOT ----------
intents = nextcord.Intents.all()
bot = commands.Bot(command_prefix="/", intents=intents)

# IDs allowed to use /setforever
ALLOWED_USERS = {1438813958848122924, 1421553185943978109, 1284809746775408682}

# ---------- SONG LIST ----------
SONG_FOLDER = "songs"
playlist = [f"{SONG_FOLDER}/{f}" for f in os.listdir(SONG_FOLDER) if f.endswith(".mp3")]

current_song_index = 0


# ---------- MUSIC PLAYER ----------
async def play_loop(vc):
    global current_song_index

    while True:
        if not vc.is_connected():
            break

        song = playlist[current_song_index]

        vc.play(
            nextcord.FFmpegPCMAudio(song),
            after=lambda e: print(f"Finished: {song}, error: {e}")
        )

        # Wait until song finishes
        while vc.is_playing():
            await asyncio.sleep(1)

        # Next track
        current_song_index = (current_song_index + 1) % len(playlist)


# ---------- SLASH COMMAND ----------
@bot.slash_command(name="setforever", description="Makes the bot join your voice channel and start 24/7 music.")
async def set_forever(inter: Interaction):

    if inter.user.id not in ALLOWED_USERS:
        await inter.response.send_message("❌ You are not allowed to use this command.", ephemeral=True)
        return

    if inter.user.voice is None:
        await inter.response.send_message("❌ Join a voice channel first.", ephemeral=True)
        return

    channel = inter.user.voice.channel

    try:
        vc = await channel.connect()
    except:
        vc = inter.guild.voice_client
        if vc:
            await vc.move_to(channel)
        else:
            await inter.response.send_message("⚠️ Error joining VC.", ephemeral=True)
            return

    await inter.response.send_message(f"🎵 Connected to **{channel.name}** — starting 24/7 music autoplay!")

    # Start autoplay loop
    bot.loop.create_task(play_loop(vc))


# ---------- AUTORESPONDER ----------
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if "<@1284809746775408682>" in message.content:
        await message.channel.send("😡 Don't try to flirt with him, he is my man 😘🥰")

    await bot.process_commands(message)

# ---------- START BOT ----------
bot.run(DISCORD_TOKEN)
