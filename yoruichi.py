# yoruichi_music_bot.py
# Nextcord + Wavelink 3.x music bot (YouTube only)
# Features:
#  - /setchannel, /removevc (owner-role or OWNER_ID only, persistent)
#  - 24/7 presence in VC until /removevc
#  - /play (searches YouTube or accepts YT link)
#  - persistent queue per guild, /queue (paged), /clearqueue, /remove, /move, /shuffle
#  - embed with persistent controls and loop buttons (Option C: Loop Song, Loop Queue, Disable Loop)
#  - volume, seek (+/-10s), pause/resume/skip/stop
#  - /fm, /dm (FM URL support)
#  - Owner role lock: role id 1436411629741801482 unlocks owner commands
#  - stores config in config.json

import os
import json
import random
import asyncio
from typing import List, Optional
from math import floor

import nextcord
from nextcord import Interaction, SlashOption
from nextcord.ext import commands
from nextcord.ui import View, button, Button
import wavelink
from wavelink import YouTubeTrack

# ---------- CONFIG / PERSISTENCE ----------
CONFIG_FILE = "config.json"

def load_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        cfg = {"vc_channel_id": None, "stay_24_7": True}
        save_config(cfg)
        return cfg
    except Exception:
        return {"vc_channel_id": None, "stay_24_7": True}

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

cfg = load_config()

# ---------- ENV / CONSTANTS ----------
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
# fallback numeric owner id (optional)
OWNER_ID = int(os.getenv("OWNER_ID", "1355140133661184221"))
# Owner role id you gave:
OWNER_ROLE_ID = 1436411629741801482

LAVALINK_HOST = os.getenv("LAVALINK_HOST", "lavalink.dev")
LAVALINK_PORT = int(os.getenv("LAVALINK_PORT", 2333))
LAVALINK_PASSWORD = os.getenv("LAVALINK_PASSWORD", "youshallnotpass")
FM_URLS = [u.strip() for u in os.getenv("FM_URLS", "").split(",") if u.strip()]

# ---------- BOT ----------
intents = nextcord.Intents.all()
bot = commands.Bot(command_prefix="/", intents=intents)

# ---------- PERMISSION HELPERS ----------
def has_owner_role(inter: Interaction) -> bool:
    """
    Return True if the invoking user either:
      - has the configured owner role (OWNER_ROLE_ID), OR
      - matches numeric OWNER_ID (env var)
    """
    try:
        # Interaction user is typically a Member in guild interactions
        member = inter.user
        # allow owner id fallback
        if getattr(member, "id", None) == OWNER_ID:
            return True
        # check roles if available
        roles = getattr(member, "roles", None)
        if roles:
            return any(getattr(r, "id", None) == OWNER_ROLE_ID for r in roles)
    except Exception:
        pass
    return False

# convenience check used when we need to block
def require_owner(inter: Interaction) -> bool:
    return has_owner_role(inter)

# ---------- CONFIG HELPERS ----------
def get_vc_channel_id():
    return cfg.get("vc_channel_id")

def set_vc_channel_id(cid):
    cfg["vc_channel_id"] = cid
    save_config(cfg)

def stay_24_7_enabled():
    return cfg.get("stay_24_7", True)

# ---------- WAVELINK NODE ----------
@bot.event
async def on_ready():
    print(f"[READY] {bot.user} ({bot.user.id})")
    try:
        if not wavelink.NodePool.nodes:
            await wavelink.NodePool.create_node(
                bot=bot,
                host=LAVALINK_HOST,
                port=LAVALINK_PORT,
                password=LAVALINK_PASSWORD,
                https=False,
                identifier="MAIN"
            )
            print("[Wavelink] Node created.")
        else:
            print("[Wavelink] Node(s) already exist.")
    except Exception as e:
        print("[Wavelink] Failed to create node:", e)

# ---------- PLAYER HELPERS ----------
async def ensure_player_for_guild(guild: nextcord.Guild, vc_channel_id: Optional[int]=None) -> Optional[wavelink.Player]:
    if not wavelink.NodePool.nodes:
        return None
    node = next(iter(wavelink.NodePool.nodes.values()))
    try:
        player = node.get_player(guild.id)
    except Exception:
        player = wavelink.Player(bot=bot, guild_id=guild.id)
    # connect if not connected
    if not player.is_connected():
        target_vc_id = vc_channel_id or get_vc_channel_id()
        if not target_vc_id:
            return None
        channel = bot.get_channel(target_vc_id)
        if not channel:
            return None
        try:
            await player.connect(channel.id)
        except Exception as e:
            try:
                await channel.connect(cls=wavelink.Player)
                # refresh player
                node = next(iter(wavelink.NodePool.nodes.values()))
                player = node.get_player(guild.id)
            except Exception as e2:
                print("Failed to connect player:", e, e2)
                return None
    # ensure queue, loop, volume attributes exist
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

def progress_bar(position_ms: int, total_ms: Optional[int], length: int = 20) -> str:
    if total_ms is None or total_ms <= 0:
        pos = (position_ms // 1000) % length
        bar = ["▬"] * length
        bar[pos % length] = "🔘"
        return "".join(bar)
    p = max(0.0, min(1.0, position_ms / total_ms))
    filled = int(p * length)
    bar = "▬" * filled + "🔘" + "▬" * max(0, length - filled - 1)
    return bar

# ---------- PERSISTENT MUSIC CONTROLS VIEW ----------
class MusicControls(nextcord.ui.View):
    def __init__(self, player: wavelink.Player):
        super().__init__(timeout=None)
        self.player = player

    @nextcord.ui.button(label="▶ Resume", style=nextcord.ButtonStyle.success, custom_id="music_resume")
    async def resume_button(self, b: Button, inter: Interaction):
        try:
            await self.player.resume()
            await inter.response.send_message("▶ Resumed", ephemeral=True)
        except Exception as e:
            await inter.response.send_message(f"Resume failed: {e}", ephemeral=True)

    @nextcord.ui.button(label="⏸ Pause", style=nextcord.ButtonStyle.primary, custom_id="music_pause")
    async def pause_button(self, b: Button, inter: Interaction):
        try:
            await self.player.pause()
            await inter.response.send_message("⏸ Paused", ephemeral=True)
        except Exception as e:
            await inter.response.send_message(f"Pause failed: {e}", ephemeral=True)

    @nextcord.ui.button(label="⏭ Skip", style=nextcord.ButtonStyle.secondary, custom_id="music_skip")
    async def skip_button(self, b: Button, inter: Interaction):
        try:
            await self.player.stop()
            await inter.response.send_message("⏭ Skipped", ephemeral=True)
        except Exception as e:
            await inter.response.send_message(f"Skip failed: {e}", ephemeral=True)

    @nextcord.ui.button(label="⏹ Stop", style=nextcord.ButtonStyle.danger, custom_id="music_stop")
    async def stop_button(self, b: Button, inter: Interaction):
        # only owner-role or owner-id can stop/disconnect via the UI too
        if not has_owner_role(inter):
            await inter.response.send_message("You don't have permission to stop the bot.", ephemeral=True)
            return
        try:
            await self.player.disconnect()
            await inter.response.send_message("Stopped & disconnected.", ephemeral=True)
        except Exception as e:
            await inter.response.send_message(f"Stop failed: {e}", ephemeral=True)

    @nextcord.ui.button(label="🔁 Loop Song", style=nextcord.ButtonStyle.success, custom_id="loop_song")
    async def loop_song_button(self, b: Button, inter: Interaction):
        try:
            self.player.loop = "song"
            await inter.response.send_message("Loop mode: Song 🔁", ephemeral=True)
        except Exception as e:
            await inter.response.send_message(f"Error: {e}", ephemeral=True)

    @nextcord.ui.button(label="🔁🔁 Loop Queue", style=nextcord.ButtonStyle.success, custom_id="loop_queue")
    async def loop_queue_button(self, b: Button, inter: Interaction):
        try:
            self.player.loop = "queue"
            await inter.response.send_message("Loop mode: Queue 🔁🔁", ephemeral=True)
        except Exception as e:
            await inter.response.send_message(f"Error: {e}", ephemeral=True)

    @nextcord.ui.button(label="🚫 Disable Loop", style=nextcord.ButtonStyle.secondary, custom_id="loop_off")
    async def loop_off_button(self, b: Button, inter: Interaction):
        try:
            self.player.loop = False
            await inter.response.send_message("Loop disabled 🚫", ephemeral=True)
        except Exception as e:
            await inter.response.send_message(f"Error: {e}", ephemeral=True)

    @nextcord.ui.button(label="🔀 Shuffle", style=nextcord.ButtonStyle.primary, custom_id="shuffle")
    async def shuffle_button(self, b: Button, inter: Interaction):
        try:
            if hasattr(self.player, "queue") and self.player.queue:
                random.shuffle(self.player.queue)
                await inter.response.send_message("🔀 Queue shuffled", ephemeral=True)
            else:
                await inter.response.send_message("Queue empty", ephemeral=True)
        except Exception as e:
            await inter.response.send_message(f"Error: {e}", ephemeral=True)

    @nextcord.ui.button(label="🔊 +", style=nextcord.ButtonStyle.primary, custom_id="vol_up")
    async def vol_up(self, b: Button, inter: Interaction):
        try:
            vol = getattr(self.player, "volume", 100)
            vol = min(200, vol + 10)
            await self.player.set_volume(vol)
            self.player.volume = vol
            await inter.response.send_message(f"Volume: {vol}%", ephemeral=True)
        except Exception as e:
            await inter.response.send_message(f"Volume change failed: {e}", ephemeral=True)

    @nextcord.ui.button(label="🔉 -", style=nextcord.ButtonStyle.primary, custom_id="vol_down")
    async def vol_down(self, b: Button, inter: Interaction):
        try:
            vol = getattr(self.player, "volume", 100)
            vol = max(0, vol - 10)
            await self.player.set_volume(vol)
            self.player.volume = vol
            await inter.response.send_message(f"Volume: {vol}%", ephemeral=True)
        except Exception as e:
            await inter.response.send_message(f"Volume change failed: {e}", ephemeral=True)

    @nextcord.ui.button(label="⏪ -10s", style=nextcord.ButtonStyle.secondary, custom_id="seek_back")
    async def seek_back(self, b: Button, inter: Interaction):
        try:
            pos = getattr(self.player, "position", 0)
            new = max(0, pos - 10000)
            try:
                await self.player.seek(new)
                await inter.response.send_message("⏪ Seeked -10s", ephemeral=True)
            except Exception:
                await inter.response.send_message("Seek not supported on this player", ephemeral=True)
        except Exception as e:
            await inter.response.send_message(f"Error: {e}", ephemeral=True)

    @nextcord.ui.button(label="⏩ +10s", style=nextcord.ButtonStyle.secondary, custom_id="seek_forward")
    async def seek_forward(self, b: Button, inter: Interaction):
        try:
            pos = getattr(self.player, "position", 0)
            new = pos + 10000
            try:
                await self.player.seek(new)
                await inter.response.send_message("⏩ Seeked +10s", ephemeral=True)
            except Exception:
                await inter.response.send_message("Seek not supported on this player", ephemeral=True)
        except Exception as e:
            await inter.response.send_message(f"Error: {e}", ephemeral=True)

# ---------- SLASH COMMANDS ----------
@bot.slash_command(description="Set the VC channel to use for 24/7 (owner-role or owner-id only)")
async def setchannel(inter: Interaction, channel: nextcord.VoiceChannel):
    if not require_owner(inter):
        await inter.response.send_message("❌ You need the owner role or be the bot owner to use this.", ephemeral=True)
        return
    set_vc_channel_id(channel.id)
    player = await ensure_player_for_guild(inter.guild, vc_channel_id=channel.id)
    if player:
        await inter.response.send_message(f"Channel set to {channel.name} ✅ (joined).", ephemeral=False)
    else:
        await inter.response.send_message(f"Channel set to {channel.name} ✅ (but failed to auto-join).", ephemeral=False)

@bot.slash_command(description="Remove 24/7 VC and disconnect (owner-role or owner-id only)")
async def removevc(inter: Interaction):
    if not require_owner(inter):
        await inter.response.send_message("❌ You need the owner role or be the bot owner to use this.", ephemeral=True)
        return
    cid = get_vc_channel_id()
    if not cid:
        await inter.response.send_message("No VC configured.", ephemeral=True)
        return
    channel = bot.get_channel(cid)
    player = None
    try:
        node = next(iter(wavelink.NodePool.nodes.values()))
        player = node.get_player(inter.guild.id)
    except Exception:
        player = None
    if player and player.is_connected():
        try:
            await player.disconnect()
        except Exception:
            pass
    set_vc_channel_id(None)
    await inter.response.send_message("Removed 24/7 VC and disconnected.", ephemeral=False)

@bot.slash_command(description="Play a song (searches YouTube or accepts YT link)")
async def play(inter: Interaction, query: str):
    await inter.response.defer()
    cid = get_vc_channel_id()
    if not cid:
        await inter.followup.send("VC not set. Use /setchannel first.", ephemeral=True)
        return
    channel = bot.get_channel(cid)
    if not channel:
        await inter.followup.send("Saved VC channel not found. Use /setchannel again.", ephemeral=True)
        return

    player = await ensure_player_for_guild(inter.guild, vc_channel_id=cid)
    if not player:
        await inter.followup.send("Failed to prepare player. Check Lavalink node and config.", ephemeral=True)
        return

    try:
        track = await YouTubeTrack.search(query, return_first=True)
    except Exception as e:
        await inter.followup.send(f"Search failed: {e}", ephemeral=True)
        return

    if not track:
        await inter.followup.send("No results.", ephemeral=True)
        return

    if player.is_playing() or player.is_paused():
        player.queue.append(track)
        await inter.followup.send(f"Queued: **{track.title}**", ephemeral=False)
        return

    try:
        await player.play(track)
    except Exception as e:
        await inter.followup.send(f"Play failed: {e}", ephemeral=True)
        return

    embed = nextcord.Embed(title="Now Playing", description=f"**{track.title}**", color=0x00ff88)
    embed.add_field(name="Author", value=track.author, inline=True)
    embed.add_field(name="Duration", value=format_duration(track.length), inline=True)
    thumb = getattr(track, "thumbnail", None)
    if thumb:
        embed.set_thumbnail(url=thumb)
    embed.set_footer(text=f"Requested by {inter.user.display_name}")

    view = MusicControls(player)
    await inter.followup.send(embed=embed, view=view)

@bot.slash_command(description="Pause playback")
async def pause(inter: Interaction):
    await inter.response.defer(ephemeral=True)
    player = await ensure_player_for_guild(inter.guild)
    if not player:
        await inter.followup.send("Player not found.", ephemeral=True)
        return
    await player.pause()
    await inter.followup.send("⏸ Paused", ephemeral=True)

@bot.slash_command(description="Resume playback")
async def resume(inter: Interaction):
    await inter.response.defer(ephemeral=True)
    player = await ensure_player_for_guild(inter.guild)
    if not player:
        await inter.followup.send("Player not found.", ephemeral=True)
        return
    await player.resume()
    await inter.followup.send("▶️ Resumed", ephemeral=True)

@bot.slash_command(description="Skip current")
async def skip(inter: Interaction):
    await inter.response.defer(ephemeral=True)
    player = await ensure_player_for_guild(inter.guild)
    if not player:
        await inter.followup.send("Player not found.", ephemeral=True)
        return
    await player.stop()
    await inter.followup.send("⏭ Skipped", ephemeral=True)

@bot.slash_command(description="Stop and disconnect (owner-role or owner-id only)")
async def stop(inter: Interaction):
    if not require_owner(inter):
        await inter.response.send_message("❌ You need the owner role or be the bot owner to use this.", ephemeral=True)
        return
    player = await ensure_player_for_guild(inter.guild)
    if player and player.is_connected():
        await player.disconnect()
    await inter.response.send_message("Stopped and disconnected.", ephemeral=False)

# Queue commands
@bot.slash_command(description="Show upcoming songs (paged)")
async def queue_cmd(inter: Interaction, page: int = SlashOption(default=1, description="Page number")):
    await inter.response.defer()
    player = await ensure_player_for_guild(inter.guild)
    if not player:
        await inter.followup.send("Player not found.", ephemeral=True)
        return
    q: List[YouTubeTrack] = getattr(player, "queue", [])
    if not q:
        await inter.followup.send("Queue is empty.", ephemeral=True)
        return
    per_page = 10
    total_pages = (len(q) + per_page - 1) // per_page
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    end = start + per_page
    embed = nextcord.Embed(title=f"Queue — Page {page}/{total_pages}", color=0x00ddff)
    for i, t in enumerate(q[start:end], start=start + 1):
        embed.add_field(name=f"{i}.", value=f"{t.title}", inline=False)
    await inter.followup.send(embed=embed, ephemeral=False)

@bot.slash_command(description="Clear the queue")
async def clearqueue(inter: Interaction):
    player = await ensure_player_for_guild(inter.guild)
    if not player:
        await inter.response.send_message("Player not found.", ephemeral=True)
        return
    player.queue = []
    await inter.response.send_message("🗑 Queue cleared.", ephemeral=False)

@bot.slash_command(description="Remove a track from queue by index (1-based)")
async def remove(inter: Interaction, index: int = SlashOption(description="1-based index of queued song")):
    player = await ensure_player_for_guild(inter.guild)
    if not player:
        await inter.response.send_message("Player not found.", ephemeral=True)
        return
    q = getattr(player, "queue", [])
    if not q or index < 1 or index > len(q):
        await inter.response.send_message("Invalid index.", ephemeral=True)
        return
    removed = q.pop(index - 1)
    await inter.response.send_message(f"Removed **{removed.title}** from queue.", ephemeral=False)

@bot.slash_command(description="Move a queued song from one position to another (1-based)")
async def move(inter: Interaction, from_index: int = SlashOption(description="from index"), to_index: int = SlashOption(description="to index")):
    player = await ensure_player_for_guild(inter.guild)
    if not player:
        await inter.response.send_message("Player not found.", ephemeral=True)
        return
    q = getattr(player, "queue", [])
    n = len(q)
    if not q or from_index < 1 or from_index > n or to_index < 1 or to_index > n:
        await inter.response.send_message("Invalid indices.", ephemeral=True)
        return
    item = q.pop(from_index - 1)
    q.insert(to_index - 1, item)
    await inter.response.send_message(f"Moved **{item.title}** to position {to_index}.", ephemeral=False)

@bot.slash_command(description="Shuffle the queue")
async def shuffle(inter: Interaction):
    player = await ensure_player_for_guild(inter.guild)
    if not player:
        await inter.response.send_message("Player not found.", ephemeral=True)
        return
    if getattr(player, "queue", None):
        random.shuffle(player.queue)
        await inter.response.send_message("🔀 Queue shuffled.", ephemeral=False)
    else:
        await inter.response.send_message("Queue is empty.", ephemeral=True)

@bot.slash_command(description="Set volume (0-200) (owner-role or owner-id only)")
async def volume(inter: Interaction, vol: int = SlashOption(min_value=0, max_value=200)):
    if not require_owner(inter):
        await inter.response.send_message("❌ You need the owner role or be the bot owner to use this.", ephemeral=True)
        return
    player = await ensure_player_for_guild(inter.guild)
    if not player:
        await inter.response.send_message("Player not found.", ephemeral=True)
        return
    await player.set_volume(vol)
    player.volume = vol
    await inter.response.send_message(f"Volume set to {vol}%", ephemeral=False)

@bot.slash_command(description="Seek relative seconds (positive or negative)")
async def seek(inter: Interaction, seconds: int = SlashOption(description="Seconds to seek (+/-)")):
    player = await ensure_player_for_guild(inter.guild)
    if not player:
        await inter.response.send_message("Player not found.", ephemeral=True)
        return
    pos = getattr(player, "position", 0)
    new = max(0, pos + seconds * 1000)
    try:
        await player.seek(new)
        await inter.response.send_message(f"Seeked to {format_duration(new)}", ephemeral=False)
    except Exception:
        await inter.response.send_message("Seek not supported on this track/player.", ephemeral=True)

@bot.slash_command(description="Play an FM stream or random configured FM")
async def fm(inter: Interaction, url: str = SlashOption(default=None, description="Stream URL (optional)")):
    cid = get_vc_channel_id()
    if not cid:
        await inter.response.send_message("VC not set.", ephemeral=True)
        return
    player = await ensure_player_for_guild(inter.guild, vc_channel_id=cid)
    if not player:
        await inter.response.send_message("Player error.", ephemeral=True)
        return
    if not url:
        if not FM_URLS:
            await inter.response.send_message("No FM URLs configured in FM_URLS env var.", ephemeral=True)
            return
        url = random.choice(FM_URLS)
    try:
        track = wavelink.Track(uri=url, title="FM Stream")
        await player.play(track)
        await inter.response.send_message(f"Playing FM: {url}", ephemeral=False)
    except Exception as e:
        await inter.response.send_message(f"Failed to play FM: {e}", ephemeral=True)

@bot.slash_command(description="DM you a random FM URL")
async def dm(inter: Interaction):
    if not FM_URLS:
        await inter.response.send_message("No FM URLs configured.", ephemeral=True)
        return
    url = random.choice(FM_URLS)
    try:
        await inter.user.send(f"Your random FM: {url}")
        await inter.response.send_message("Sent DM with FM URL ✅", ephemeral=True)
    except Exception:
        await inter.response.send_message("Couldn't send DM (maybe DMs are closed).", ephemeral=True)

# ---------- TRACK END HANDLER ----------
@bot.listen()
async def on_wavelink_track_end(payload: wavelink.TrackEndEventPayload):
    try:
        player = payload.player
    except Exception:
        return

    # loop song
    if getattr(player, "loop", False) == "song" and getattr(payload, "track", None):
        try:
            await player.play(payload.track)
            return
        except Exception:
            pass

    q = getattr(player, "queue", [])
    if q:
        next_track = q.pop(0)
        try:
            await player.play(next_track)
            return
        except Exception:
            pass

    if getattr(player, "loop", False) == "queue" and getattr(payload, "track", None):
        try:
            await player.play(payload.track)
            return
        except Exception:
            pass

    if stay_24_7_enabled():
        return

    try:
        await player.disconnect()
    except Exception:
        pass

# ---------- AUTORESPONDER ----------
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if "<@1284809746775408682>" in message.content:
        await message.channel.send("😡 Don't try to flirt with him, he is my man 😘🥰")
    await bot.process_commands(message)

# ---------- START ----------
if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("Please set DISCORD_TOKEN env var.")
    else:
        bot.run(DISCORD_TOKEN)
