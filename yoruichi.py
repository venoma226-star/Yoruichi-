import os
import json
import random
import asyncio
import threading

import nextcord
from nextcord import Interaction
from nextcord.ext import commands
from nextcord.ui import View
from flask import Flask
import yt_dlp

# ---------- FLASK KEEP-ALIVE ----------
app = Flask("")

@app.route("/")
def home():
    return "Yoruichi Bot is alive!"

threading.Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))).start()

# ---------- CONFIG ----------
CONFIG_FILE = "config.json"

def load_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        cfg = {"vc_channel_id": None, "queue": [], "loop": False}
        save_config(cfg)
        return cfg

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

cfg = load_config()

# ---------- ENV ----------
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "1355140133661184221"))
OWNER_ROLE_ID = int(os.getenv("OWNER_ROLE_ID", 1436411629741801482))

# ---------- DEFAULT 24/7 VC ----------
DEFAULT_VC_ID = 1440192154029916252

# ---------- BOT ----------
intents = nextcord.Intents.all()
bot = commands.Bot(command_prefix="/", intents=intents)

# ---------- OWNER CHECK ----------
def has_owner_role(inter: Interaction) -> bool:
    member = inter.user
    if member.id == OWNER_ID:
        return True
    return any(r.id == OWNER_ROLE_ID for r in getattr(member, "roles", []))

def require_owner(inter: Interaction):
    return has_owner_role(inter)

# ---------- VC HANDLING ----------
def get_vc_channel_id():
    return cfg.get("vc_channel_id") or DEFAULT_VC_ID

def set_vc_channel_id(cid):
    cfg["vc_channel_id"] = cid
    save_config(cfg)

async def get_voice_client(guild: nextcord.Guild, channel_id=None):
    channel_id = channel_id or get_vc_channel_id()
    if not channel_id:
        return None
    channel = guild.get_channel(channel_id)
    if not channel:
        try:
            channel = await bot.fetch_channel(channel_id)
        except:
            return None
    if guild.voice_client:
        return guild.voice_client
    return await channel.connect()

# ---------- MUSIC QUEUE ----------
cfg["queue"] = cfg.get("queue", [])
cfg["loop"] = cfg.get("loop", False)

async def play_next(vc: nextcord.VoiceClient):
    if not cfg["queue"]:
        return

    query = cfg["queue"][0]

    ydl_opts = {"format": "bestaudio", "quiet": True, "noplaylist": True}

    if not query.startswith("http"):
        query = f"ytsearch1:{query}"

    def run_yt():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)
            url = info["entries"][0]["url"] if "entries" in info else info["url"]
            title = info["entries"][0]["title"] if "entries" in info else info.get("title", "Unknown")
            return url, title

    audio_url, title = await asyncio.to_thread(run_yt)

    vc.play(nextcord.FFmpegPCMAudio(audio_url, options="-vn"), after=lambda e: asyncio.run_coroutine_threadsafe(after_play(vc), bot.loop))

    embed = nextcord.Embed(title="Now Playing", description=f"**{title}**", color=0x00ff88)
    return embed

async def after_play(vc: nextcord.VoiceClient):
    if cfg["loop"] and cfg["queue"]:
        # Loop queue: move first track to end
        cfg["queue"].append(cfg["queue"].pop(0))
    else:
        if cfg["queue"]:
            cfg["queue"].pop(0)
    if cfg["queue"]:
        embed = await play_next(vc)
        channel = vc.channel
        if channel:
            await channel.send(embed=embed, view=MusicControls(vc))

# ---------- AUTORESPONDER ----------
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if "<@1284809746775408682>" in message.content:
        await message.channel.send("😡 Don't try to flirt with him, he is my man 😘🥰")
    await bot.process_commands(message)

# ---------- MUSIC CONTROLS ----------
class MusicControls(View):
    def __init__(self, vc):
        super().__init__(timeout=None)
        self.vc = vc

    @nextcord.ui.button(label="⏸ Pause", style=nextcord.ButtonStyle.primary)
    async def pause(self, b, inter: Interaction):
        if self.vc.is_playing():
            self.vc.pause()
            await inter.response.send_message("⏸ Paused", ephemeral=True)

    @nextcord.ui.button(label="▶ Resume", style=nextcord.ButtonStyle.success)
    async def resume(self, b, inter: Interaction):
        if self.vc.is_paused():
            self.vc.resume()
            await inter.response.send_message("▶ Resumed", ephemeral=True)

    @nextcord.ui.button(label="⏭ Skip", style=nextcord.ButtonStyle.secondary)
    async def skip(self, b, inter: Interaction):
        self.vc.stop()
        await inter.response.send_message("⏭ Skipped", ephemeral=True)

    @nextcord.ui.button(label="🔁 Loop Queue", style=nextcord.ButtonStyle.success)
    async def loop_queue(self, b, inter: Interaction):
        cfg["loop"] = not cfg["loop"]
        await inter.response.send_message(f"Loop is now {cfg['loop']}", ephemeral=True)

# ---------- SLASH COMMANDS ----------
@bot.slash_command(description="Set VC for 24/7 music (owner only)")
async def setchannel(inter: Interaction, channel: nextcord.VoiceChannel):
    if not require_owner(inter):
        return await inter.response.send_message("❌ Owner-role required", ephemeral=True)

    await inter.response.defer()

    async def join_vc():
        set_vc_channel_id(channel.id)
        await get_voice_client(inter.guild, channel.id)
        await inter.followup.send(f"VC set to {channel.name} ✅")

    asyncio.create_task(join_vc())

@bot.slash_command(description="Remove VC")
async def removevc(inter: Interaction):
    if not require_owner(inter):
        return await inter.response.send_message("❌ Owner-role required", ephemeral=True)
    vc = inter.guild.voice_client
    if vc:
        await vc.disconnect()
    set_vc_channel_id(None)
    await inter.response.send_message("Removed VC", ephemeral=False)

@bot.slash_command(description="Play song (search or link)")
async def play(inter: Interaction, query: str):
    await inter.response.defer()

    async def do_play():
        vc = await get_voice_client(inter.guild)
        if not vc:
            return await inter.followup.send("VC not set or bot not connected.", ephemeral=True)

        cfg["queue"].append(query)

        if not vc.is_playing() and not vc.is_paused():
            embed = await play_next(vc)
            await inter.followup.send(embed=embed, view=MusicControls(vc))
        else:
            await inter.followup.send(f"Added to queue: {query}")

    asyncio.create_task(do_play())

@bot.slash_command(description="Show queue")
async def queue(inter: Interaction):
    if not cfg["queue"]:
        return await inter.response.send_message("Queue is empty", ephemeral=True)
    desc = "\n".join([f"{i+1}. {t}" for i, t in enumerate(cfg["queue"])])
    await inter.response.send_message(f"**Queue:**\n{desc}")

@bot.slash_command(description="Clear queue")
async def clearqueue(inter: Interaction):
    cfg["queue"].clear()
    await inter.response.send_message("🗑️ Queue cleared", ephemeral=False)

# ---------- START BOT ----------
async def auto_join_24_7():
    await bot.wait_until_ready()
    await asyncio.sleep(2)
    vc_id = get_vc_channel_id()
    if vc_id:
        for guild in bot.guilds:
            channel = guild.get_channel(vc_id)
            if not channel:
                try:
                    channel = await bot.fetch_channel(vc_id)
                except:
                    continue
            if channel and isinstance(channel, nextcord.VoiceChannel):
                if not guild.voice_client:
                    await get_voice_client(guild, vc_id)
                    print(f"[24/7] Connected to VC {channel.name}")

bot.loop.create_task(auto_join_24_7())
bot.run(DISCORD_TOKEN)
