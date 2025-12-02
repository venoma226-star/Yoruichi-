import os
import threading
import nextcord
from nextcord.ext import commands
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
