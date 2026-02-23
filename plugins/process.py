import os
import time
import asyncio
import re
import random
import string
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
    # Use message ID to make the filename unique for concurrent processing (e.g. albums)
    message_id = message.id

    # 0. Check for FFmpeg first
    if not shutil.which("ffmpeg"):
        await message.edit_text("❌ **System Error**\n\n`ffmpeg` is not installed on the server. Please contact the administrator.")
        return

    # Extract Data
    media_type = data.get("type")
    is_subtitle = data.get("is_subtitle", False)
    language = data.get("language", "en")
    tmdb_id = data.get("tmdb_id")
    title = data.get("title")
    year = data.get("year")
    poster_url = data.get("poster")
    season = data.get("season")
    episode = data.get("episode")
    quality = data.get("quality", "720p")
    file_message = data.get("file_message")
    original_name = data.get("original_name", "unknown.mkv")

    status_msg = await message.edit_text(
        "🚀 **Starting Process...**\n\n"
        "📥 **Phase 1: Downloading**\n"
        "Fetching your file from Telegram servers..."
    )

    start_time = time.time()
    # Unique input filename
    ext = ".mkv"
    if is_subtitle:
         ext = os.path.splitext(original_name)[1]
         if not ext: ext = ".srt"

    file_path = os.path.join(Config.DOWNLOAD_DIR, f"{user_id}_{message_id}_input{ext}")

    try:
        downloaded_path = await client.download_media(
            file_message,
            file_name=file_path,
            progress=progress_for_pyrogram,
            progress_args=("📥 **Downloading Media...**", status_msg, start_time)
        )

        # DEBUGGING: Verify file existence and size
        if downloaded_path and os.path.exists(downloaded_path):
            file_size = os.path.getsize(downloaded_path)
            logging.info(f"Download complete: {downloaded_path} (Size: {file_size} bytes)")
            if file_size == 0:
                await status_msg.edit_text(f"❌ **Download Error**\n\nFile size is 0 bytes.")
                return
            # Update file_path to the actual returned path (in case of extension changes)
            file_path = downloaded_path
        else:
             # DEBUG: List directory if file missing
            logging.error(f"Download reported success but file missing: {file_path}")
            if os.path.exists(Config.DOWNLOAD_DIR):
                logging.error(f"Directory contents: {os.listdir(Config.DOWNLOAD_DIR)}")

            await status_msg.edit_text(f"❌ **Download Error**\n\nFile not found after download.\nExpected: `{file_path}`")
            return

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

    # Unique thumbnail path
    thumb_path = os.path.join(Config.DOWNLOAD_DIR, f"{user_id}_{message_id}_thumb.jpg")

    if not is_subtitle:
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

        if is_subtitle:
            final_filename = f"{safe_title}.{season_episode}.{language}.srt"
        else:
            final_filename = f"{safe_title}.{season_episode}.{quality}_[@XTVglobal].mkv"

        meta_title = templates.get("title", "").format(title=title, season_episode=season_episode)
    else:
        season_episode = ""

        if is_subtitle:
            final_filename = f"{safe_title}.{year}.{language}.srt"
        else:
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

    # Check if output file already exists (race condition check)
    if os.path.exists(output_path):
         output_path = os.path.join(Config.DOWNLOAD_DIR, f"{int(time.time())}_{final_filename}")

    cmd, err = await generate_ffmpeg_command(
        input_path=file_path,
        output_path=output_path,
        metadata=metadata_dict,
        thumbnail_path=thumb_path if (os.path.exists(thumb_path) and not is_subtitle) else None
    )

    if not cmd:
        await status_msg.edit_text(f"❌ **FFmpeg Error**\n\n`{err}`")
        if os.path.exists(file_path): os.remove(file_path)
        if os.path.exists(thumb_path): os.remove(thumb_path)
        return

    success, stderr = await execute_ffmpeg(cmd)
    if not success:
        print(stderr.decode())
        await status_msg.edit_text("❌ **Encoding Failed**\n\nSomething went wrong during processing.")
        if os.path.exists(file_path): os.remove(file_path)
        if os.path.exists(thumb_path): os.remove(thumb_path)
        if os.path.exists(output_path): os.remove(output_path)
        return

    # 3. Upload
    await status_msg.edit_text(
        "📤 **Phase 3: Uploading**\n\n"
        "Sending the renamed file back to you..."
    )

    start_time = time.time()

    # Generate Caption
    caption_template = templates.get("caption", "{random}")
    if "{random}" in caption_template or caption_template == "{random}":
        # Generate random string to bypass hash detection
        random_str = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
        final_caption = random_str
    else:
        # Helper to get human readable size
        def humanbytes(size):
            if not size: return ""
            power = 2**10
            n = 0
            Dic_powerN = {0: ' ', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
            while size > power:
                size /= power
                n += 1
            return str(round(size, 2)) + " " + Dic_powerN[n] + 'B'

        file_size_str = humanbytes(os.path.getsize(output_path))
        # We don't have duration easily available without probing again, so we'll skip duration for now or default
        final_caption = caption_template.format(
            filename=final_filename,
            size=file_size_str,
            duration="", # Placeholder
            random=''.join(random.choices(string.ascii_letters + string.digits, k=8))
        )

    try:
        await client.send_document(
            chat_id=message.chat.id,
            document=output_path,
            thumb=thumb_path if os.path.exists(thumb_path) else None,
            caption=final_caption,
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
