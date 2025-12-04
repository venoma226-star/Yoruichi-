import os
import threading
import random
import nextcord
from nextcord.ext import commands
from flask import Flask

# ---------- FLASK KEEP-ALIVE ----------
app = Flask("")

@app.route("/")
def home():
    return "Bot is alive!"

def run_flask():
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)))

threading.Thread(target=run_flask).start()

# ---------- BOT SETUP ----------
intents = nextcord.Intents.all()
bot = commands.Bot(command_prefix="/", intents=intents)

AUTHORIZED = {1438813958848122924, 1421553185943978109, 1284809746775408682}

# ---------- MUSIC LOOP ----------
songs_folder = "songs"

def get_song_list():
    try:
        return [f"songs/{f}" for f in os.listdir(songs_folder) if f.endswith(".mp3")]
    except:
        return []

async def play_loop(voice_client):
    while True:
        songs = get_song_list()
        if not songs:
            return
        song = random.choice(songs)
        voice_client.play(
            nextcord.FFmpegPCMAudio(song),
            after=lambda e: None
        )
        while voice_client.is_playing():
            await nextcord.utils.sleep_until(nextcord.utils.utcnow() + nextcord.utils.timedelta(seconds=1))

# ---------- SLASH COMMAND ----------
@bot.slash_command(name="setforever", description="Bot joins your VC & plays music forever")
async def setforever(interaction: nextcord.Interaction):

    # Permission check for 3 IDs
    if interaction.user.id not in AUTHORIZED:
        return await interaction.response.send_message("❌ You are not allowed to use this command.", ephemeral=True)

    # Must be in VC
    if interaction.user.voice is None:
        return await interaction.response.send_message("❌ Join a voice channel first.", ephemeral=True)

    channel = interaction.user.voice.channel

    # Connect or move
    voice = nextcord.utils.get(bot.voice_clients, guild=interaction.guild)

    if not voice:
        voice = await channel.connect()
    else:
        await voice.move_to(channel)

    await interaction.response.send_message(f"✅ Joined **{channel.name}** and will play music 24/7.")

    # Start loop
    bot.loop.create_task(play_loop(voice))

# ---------- AUTORESPONDER ----------
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if "<@1284809746775408682>" in message.content:
        await message.channel.send("😡 Don't try to flirt with him, he is my man 😘🥰")

    await bot.process_commands(message)

# ---------- RUN ----------
TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
