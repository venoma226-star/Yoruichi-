import os
import nextcord
from nextcord.ext import commands
from nextcord import Interaction
import asyncio
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
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_flask, daemon=True).start()

# -------------------------
# DISCORD BOT SETUP
# -------------------------
intents = nextcord.Intents.all()
bot = commands.Bot(intents=intents)

ALLOWED_ROLE = 1436411629741801482

ffmpeg_options = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -re",
    "options": "-vn"
}

# -------------------------
# PLAYLIST WITH DIRECT MP3 LINKS
# -------------------------
PLAYLIST = [
    "https://cdn.discordapp.com/attachments/1440192154029916252/1446004021612642324/Adore_-_Did_I_Tell_U_That_I_Miss_U_SkySound.cc.mp3",
    "https://cdn.discordapp.com/attachments/1440192154029916252/1446004022493577266/Don_Toilver_-_No_pole_mp3.pm.mp3",
    "https://cdn.discordapp.com/attachments/1440192154029916252/1446004023013544016/Golden-Brown-The-Stranglers-Slowed-Reverb-1.mp3",
    "https://cdn.discordapp.com/attachments/1440192154029916252/1446004023412133888/-_u_weren_t_here_I_really_miss_you_mp3.pm.mp3",
    "https://cdn.discordapp.com/attachments/1440192154029916252/1446004024267509822/soundcloudaud.com_Rukia_Kuchiki_Bankai_x_U_Werent_Here_I_Really_Miss_U_best_part_looped_SwoleRuto_Edit.mp3",
    "https://cdn.discordapp.com/attachments/1440192154029916252/1446004024670290030/wiv_-_i_love_u._slowed_SkySound.cc.mp3"
]

current_index = 0

# -------------------------
# AUTO-LOOP PLAYER
# -------------------------
async def autoplay_loop(vc):
    global current_index

    await asyncio.sleep(0.5)  # small delay to stabilize VC

    while vc.is_connected():
        try:
            source = nextcord.FFmpegPCMAudio(PLAYLIST[current_index], **ffmpeg_options)
            
            play_done = asyncio.Event()
            def after_play(error):
                if error:
                    print(f"Error in after_play: {error}")
                bot.loop.call_soon_threadsafe(play_done.set)

            vc.play(source, after=after_play)
            print(f"Playing: {PLAYLIST[current_index]}")

            await play_done.wait()  # wait for track to finish
            current_index = (current_index + 1) % len(PLAYLIST)

        except Exception as e:
            print(f"Error in autoplay_loop: {e}")
            await asyncio.sleep(1)

# -------------------------
# SLASH COMMANDS
# -------------------------
@bot.slash_command(name="join", description="Bot joins VC & plays music")
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

@bot.slash_command(name="leave", description="Bot disconnects")
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

@bot.slash_command(name="skip", description="Skip current track")
async def skip(interaction: Interaction):
    await interaction.response.defer()
    roles = [r.id for r in interaction.user.roles]
    if ALLOWED_ROLE not in roles:
        return await interaction.followup.send("❌ No permission.", ephemeral=True)

    vc = interaction.guild.voice_client
    if vc and vc.is_playing():
        vc.stop()
        await interaction.followup.send("⏭ Skipped current track")
    else:
        await interaction.followup.send("❌ Nothing is playing", ephemeral=True)

# -------------------------
# AUTORESPONDER TO HANOK PINGS ONLY
# -------------------------
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Ignore replies
    if message.reference is not None:
        await bot.process_commands(message)
        return

    # Respond only if Hanok is pinged
    for user in message.mentions:
        if user.id == 1284809746775408682:  # Hanok's ID
            await message.channel.send("😡 Don't try to flirt with him, he is my man 😘🥰")
            break

    await bot.process_commands(message)

# -------------------------
# READY EVENT
# -------------------------
@bot.event
async def on_ready():
    print(f"Bot is ready! Logged in as {bot.user}")

# -------------------------
# RUN BOT
# -------------------------
bot.run(os.getenv("DISCORD_TOKEN"))
