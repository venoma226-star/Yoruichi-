import os
import json
import random
import asyncio
from typing import Optional

import nextcord
from nextcord import Interaction
from nextcord.ext import commands
from nextcord.ui import View, Button
import wavelink

# ---------- CONFIG ----------
CONFIG_FILE = "config.json"

def load_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        cfg = {"vc_channel_id": None, "stay_24_7": True}
        save_config(cfg)
        return cfg

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

cfg = load_config()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "1355140133661184221"))
OWNER_ROLE_ID = 1436411629741801482

LAVALINK_HOST = os.getenv("LAVALINK_HOST", "lavalink.dev")
LAVALINK_PORT = int(os.getenv("LAVALINK_PORT", 2333))
LAVALINK_PASSWORD = os.getenv("LAVALINK_PASSWORD", "youshallnotpass")
FM_URLS = [u.strip() for u in os.getenv("FM_URLS", "").split(",") if u.strip()]

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

# ---------- VC ----------
def get_vc_channel_id():
    return cfg.get("vc_channel_id")

def set_vc_channel_id(cid):
    cfg["vc_channel_id"] = cid
    save_config(cfg)

# ---------- WAVELINK NODE ----------
@bot.event
async def on_ready():
    print(f"[READY] {bot.user} ({bot.user.id})")
    if not wavelink.NodePool.nodes:
        await wavelink.NodePool.create_node(
            bot=bot,
            host=LAVALINK_HOST,
            port=LAVALINK_PORT,
            password=LAVALINK_PASSWORD,
            https=False,
            identifier="MAIN"
        )
    print("[Wavelink] Node ready.")

# ---------- PLAYER ----------
async def get_player(guild: nextcord.Guild, vc_channel_id: Optional[int] = None):
    node = next(iter(wavelink.NodePool.nodes.values()))
    try:
        player = node.get_player(guild.id)
    except Exception:
        player = wavelink.Player(bot=bot, guild_id=guild.id)
    if not player.is_connected():
        target_vc = vc_channel_id or get_vc_channel_id()
        if not target_vc:
            return None
        channel = bot.get_channel(target_vc)
        if not channel:
            return None
        await player.connect(channel.id)
    if not hasattr(player, "queue"):
        player.queue = []
    if not hasattr(player, "loop"):
        player.loop = False
    if not hasattr(player, "volume"):
        player.volume = 100
    return player

# ---------- UTILS ----------
def format_duration(ms: Optional[int]) -> str:
    if ms is None:
        return "LIVE"
    s = ms // 1000
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"

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
    def __init__(self, player):
        super().__init__(timeout=None)
        self.player = player

    @Button(label="▶ Resume", style=nextcord.ButtonStyle.success)
    async def resume(self, b: Button, inter: Interaction):
        await self.player.resume()
        await inter.response.send_message("▶ Resumed", ephemeral=True)

    @Button(label="⏸ Pause", style=nextcord.ButtonStyle.primary)
    async def pause(self, b: Button, inter: Interaction):
        await self.player.pause()
        await inter.response.send_message("⏸ Paused", ephemeral=True)

    @Button(label="⏭ Skip", style=nextcord.ButtonStyle.secondary)
    async def skip(self, b: Button, inter: Interaction):
        await self.player.stop()
        await inter.response.send_message("⏭ Skipped", ephemeral=True)

    @Button(label="⏹ Stop", style=nextcord.ButtonStyle.danger)
    async def stop(self, b: Button, inter: Interaction):
        if not has_owner_role(inter):
            await inter.response.send_message("❌ You can't stop", ephemeral=True)
            return
        await self.player.disconnect()
        await inter.response.send_message("Stopped & disconnected", ephemeral=True)

    @Button(label="🔁 Loop Song", style=nextcord.ButtonStyle.success)
    async def loop_song(self, b: Button, inter: Interaction):
        self.player.loop = "song"
        await inter.response.send_message("Loop mode: Song 🔁", ephemeral=True)

    @Button(label="🔁🔁 Loop Queue", style=nextcord.ButtonStyle.success)
    async def loop_queue(self, b: Button, inter: Interaction):
        self.player.loop = "queue"
        await inter.response.send_message("Loop mode: Queue 🔁🔁", ephemeral=True)

    @Button(label="🚫 Disable Loop", style=nextcord.ButtonStyle.secondary)
    async def loop_off(self, b: Button, inter: Interaction):
        self.player.loop = False
        await inter.response.send_message("Loop disabled 🚫", ephemeral=True)

# ---------- SLASH COMMANDS ----------
@bot.slash_command(description="Set VC for 24/7 music")
async def setchannel(inter: Interaction, channel: nextcord.VoiceChannel):
    if not require_owner(inter):
        await inter.response.send_message("❌ Owner-role required", ephemeral=True)
        return
    set_vc_channel_id(channel.id)
    player = await get_player(inter.guild, channel.id)
    await inter.response.send_message(f"VC set to {channel.name} ✅", ephemeral=False)

@bot.slash_command(description="Remove VC and disconnect")
async def removevc(inter: Interaction):
    if not require_owner(inter):
        await inter.response.send_message("❌ Owner-role required", ephemeral=True)
        return
    player = await get_player(inter.guild)
    if player and player.is_connected():
        await player.disconnect()
    set_vc_channel_id(None)
    await inter.response.send_message("Removed 24/7 VC", ephemeral=False)

@bot.slash_command(description="Play song (search or link)")
async def play(inter: Interaction, query: str):
    await inter.response.defer()
    player = await get_player(inter.guild)
    if not player:
        return await inter.followup.send("VC not set or player error.", ephemeral=True)
    try:
        track = await wavelink.YouTubeTrack.search(query, return_first=True)
    except Exception as e:
        return await inter.followup.send(f"Search failed: {e}", ephemeral=True)
    if player.is_playing() or player.is_paused():
        player.queue.append(track)
        return await inter.followup.send(f"Queued: {track.title}")
    else:
        await player.play(track)
        embed = nextcord.Embed(title="Now Playing", description=f"**{track.title}**", color=0x00ff88)
        embed.set_footer(text=f"Requested by {inter.user.display_name}")
        await inter.followup.send(embed=embed, view=MusicControls(player))

@bot.slash_command(description="Show queue")
async def queue(inter: Interaction):
    player = await get_player(inter.guild)
    if not player or not player.queue:
        return await inter.response.send_message("Queue is empty", ephemeral=True)
    desc = "\n".join([f"{i+1}. {t.title}" for i, t in enumerate(player.queue)])
    await inter.response.send_message(f"**Queue:**\n{desc}")

@bot.slash_command(description="Clear queue")
async def clearqueue(inter: Interaction):
    player = await get_player(inter.guild)
    if player:
        player.queue.clear()
        await inter.response.send_message("🗑️ Queue cleared", ephemeral=False)

@bot.slash_command(description="Remove a song from queue by position")
async def remove(inter: Interaction, index: int):
    player = await get_player(inter.guild)
    if not player or not player.queue or index < 1 or index > len(player.queue):
        return await inter.response.send_message("Invalid index", ephemeral=True)
    track = player.queue.pop(index-1)
    await inter.response.send_message(f"Removed: {track.title}", ephemeral=False)

@bot.slash_command(description="Shuffle queue")
async def shuffle(inter: Interaction):
    player = await get_player(inter.guild)
    if not player or not player.queue:
        return await inter.response.send_message("Queue empty", ephemeral=True)
    random.shuffle(player.queue)
    await inter.response.send_message("Queue shuffled 🎲", ephemeral=False)

# ---------- AUTOPLAY NEXT ----------
@bot.event
async def on_wavelink_track_end(player: wavelink.Player, track: wavelink.Track, reason):
    """
    Autoplay next track from queue. Handles loop modes.
    """
    if hasattr(player, "loop") and player.loop == "song":
        await player.play(track)
        return

    next_track = None
    if hasattr(player, "queue") and player.queue:
        next_track = player.queue.pop(0)

    if next_track:
        await player.play(next_track)
        try:
            channel = bot.get_channel(player.channel_id)
            if channel:
                embed = nextcord.Embed(title="Now Playing", description=f"**{next_track.title}**", color=0x00ff88)
                embed.set_footer(text="Autoplayed from queue")
                await channel.send(embed=embed, view=MusicControls(player))
        except Exception:
            pass
    elif hasattr(player, "loop") and player.loop == "queue":
        if hasattr(player, "queue") and track:
            player.queue.append(track)
            next_track = player.queue.pop(0)
            await player.play(next_track)
    else:
        await player.disconnect()

# ---------- RUN ----------
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
