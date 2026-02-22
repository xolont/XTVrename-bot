import os
import time
import asyncio
import re
from pyrogram import Client
from config import Config
from database import db
from utils.ffmpeg_tools import generate_ffmpeg_command, execute_ffmpeg
from utils.progress import progress_for_pyrogram
from functools import partial
import logging
import shutil

async def process_file(client, message, data):
    user_id = message.chat.id

    # 0. Check for FFmpeg first
    if not shutil.which("ffmpeg"):
        await message.edit_text("❌ **System Error**\n\n`ffmpeg` is not installed on the server. Please contact the administrator.")
        return

    # Extract Data
    media_type = data.get("type")
    tmdb_id = data.get("tmdb_id")
    title = data.get("title")
    year = data.get("year")
    poster_url = data.get("poster")
    season = data.get("season")
    episode = data.get("episode")
    quality = data.get("quality", "720p")
    file_message = data.get("file_message")

    status_msg = await message.edit_text(
        "🚀 **Starting Process...**\n\n"
        "📥 **Phase 1: Downloading**\n"
        "Fetching your file from Telegram servers..."
    )

    start_time = time.time()
    file_path = os.path.join(Config.DOWNLOAD_DIR, f"{user_id}_input.mkv")

    try:
        await client.download_media(
            file_message,
            file_name=file_path,
            progress=progress_for_pyrogram,
            progress_args=("📥 **Downloading Media...**", status_msg, start_time)
        )
    except Exception as e:
        await status_msg.edit_text(f"❌ **Download Failed**\n\nError: `{e}`")
        return

    # 2. FFMpeg
    await status_msg.edit_text(
        "⚙️ **Phase 2: Processing**\n\n"
        "Applying Metadata & Thumbnail...\n"
        "PLEASE WAIT..."
    )

    settings = await db.get_settings()
    if settings:
        templates = settings.get("templates", Config.DEFAULT_TEMPLATES)
        thumb_binary = settings.get("thumbnail_binary")
    else:
        logging.warning("Database settings not available. Using defaults.")
        templates = Config.DEFAULT_TEMPLATES
        thumb_binary = None

    thumb_path = os.path.join(Config.DOWNLOAD_DIR, f"{user_id}_thumb.jpg")
    if thumb_binary:
        with open(thumb_path, "wb") as f:
            f.write(thumb_binary)
    else:
        if poster_url:
            import aiohttp
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(poster_url) as resp:
                        if resp.status == 200:
                            with open(thumb_path, "wb") as f:
                                f.write(await resp.read())
            except:
                pass

    sanitized_title = title.replace(" ", ".")
    safe_title = re.sub(r'[\\/*?:"<>|]', '', sanitized_title)

    if media_type == "series":
        s_str = f"S{season:02d}"
        e_str = f"E{episode:02d}"
        season_episode = f"{s_str}{e_str}"
        final_filename = f"{safe_title}.{season_episode}.{quality}_[@XTVglobal].mkv"
        meta_title = templates.get("title", "").format(title=title, season_episode=season_episode)
    else:
        season_episode = ""
        final_filename = f"{safe_title}.{quality}_[@XTVglobal].mkv"
        meta_title = templates.get("title", "").format(title=title, season_episode="").strip()

    metadata_dict = {
        "title": meta_title,
        "author": templates.get("author", ""),
        "artist": templates.get("artist", ""),
        "encoded_by": "@XTVglobal",
        "video_title": templates.get("video", "Encoded By:- @XTVglobal"),
        "audio_title": templates.get("audio", "Audio By:- @XTVglobal - {lang}"),
        "subtitle_title": templates.get("subtitle", "Subtitled By:- @XTVglobal - {lang}"),
        "default_language": "English"
    }

    output_path = os.path.join(Config.DOWNLOAD_DIR, final_filename)

    cmd, err = await generate_ffmpeg_command(
        input_path=file_path,
        output_path=output_path,
        metadata=metadata_dict,
        thumbnail_path=thumb_path if os.path.exists(thumb_path) else None
    )

    if not cmd:
        await status_msg.edit_text(f"❌ **FFmpeg Error**\n\n`{err}`")
        return

    success, stderr = await execute_ffmpeg(cmd)
    if not success:
        print(stderr.decode())
        await status_msg.edit_text("❌ **Encoding Failed**\n\nSomething went wrong during processing.")
        return

    # 3. Upload
    await status_msg.edit_text(
        "📤 **Phase 3: Uploading**\n\n"
        "Sending the renamed file back to you..."
    )

    start_time = time.time()
    try:
        await client.send_document(
            chat_id=message.chat.id,
            document=output_path,
            thumb=thumb_path if os.path.exists(thumb_path) else None,
            caption=f"✅ **{final_filename}**",
            progress=progress_for_pyrogram,
            progress_args=("📤 **Uploading...**", status_msg, start_time)
        )

        await status_msg.delete()
        await message.reply_text(
            "✅ **Task Completed Successfully!**\n\n"
            f"📂 **File:** `{final_filename}`\n"
            "🤖 **Processed by:** XTV Rename Bot\n\n"
            "Hit /new to start a new task."
        )

    except Exception as e:
        await status_msg.edit_text(f"❌ **Upload Failed**\n\nError: `{e}`")
    finally:
        if os.path.exists(file_path): os.remove(file_path)
        if os.path.exists(output_path): os.remove(output_path)
        if os.path.exists(thumb_path): os.remove(thumb_path)
