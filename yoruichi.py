import os
import threading
import nextcord
from nextcord.ext import commands
from nextcord import Interaction
from flask import Flask

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

# ---------- SYNC SLASH COMMANDS ----------
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    try:
        synced = await bot.sync_all_application_commands()
        print(f"✅ Synced {len(synced)} slash command(s).")
    except Exception as e:
        print(f"⚠️ Error syncing commands: {e}")

# ---------- SLASH COMMAND ----------
@bot.slash_command(name="setforever", description="Makes the bot join your voice channel.")
async def set_forever(inter: Interaction):

    # permission check
    if inter.user.id not in ALLOWED_USERS:
        await inter.response.send_message("❌ You are not allowed to use this command.", ephemeral=True)
        return

    # check if user is in a VC
    if inter.user.voice is None:
        await inter.response.send_message("❌ You must be **in a voice channel** first.", ephemeral=True)
        return

    channel = inter.user.voice.channel

    # connect the bot
    try:
        await channel.connect()
        await inter.response.send_message(f"✅ Joined **{channel.name}** and staying forever!")
    except:
        # if already connected, move it instead
        voice_client = inter.guild.voice_client
        if voice_client:
            await voice_client.move_to(channel)
            await inter.response.send_message(f"🔁 Moved to **{channel.name}** and staying there!")
        else:
            await inter.response.send_message("⚠️ Something went wrong.", ephemeral=True)

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
