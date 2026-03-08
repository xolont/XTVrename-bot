from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import Config
from database import db
from utils.log import get_logger
import io

logger = get_logger("plugins.public_cmds")

user_sessions = {}

def is_public_mode():
    return Config.PUBLIC_MODE

@Client.on_message(filters.command("info") & filters.private)
async def info_command(client, message):
    if not is_public_mode():
        return

    config = await db.get_public_config()
    bot_name = config.get("bot_name", "XTV Rename Bot")
    community_name = config.get("community_name", "Our Community")
    support_contact = config.get("support_contact", "@davdxpx")

    # Check if force sub is a username link
    force_sub_channel = config.get("force_sub_channel")
    channel_link = force_sub_channel if (force_sub_channel and isinstance(force_sub_channel, str) and force_sub_channel.startswith("http")) else None

    if not channel_link and force_sub_channel:
        try:
            chat_info = await client.get_chat(force_sub_channel)
            channel_link = chat_info.invite_link or f"https://t.me/{chat_info.username}"
        except:
            channel_link = "Not configured"

    if not channel_link:
        channel_link = "Not configured"

    text = f"**ℹ️ {bot_name} Info**\n\n"
    text += f"**Community:** {community_name}\n"
    text += f"**Channel Link:** {channel_link}\n"
    text += f"**Support Contact:** {support_contact}\n\n"
    text += f"------------------------\n"
    text += f"**Powered by:** 𝕏TV\n"
    text += f"**Developed by:** [𝕏0L0™](https://t.me/davdxpx)\n"

    await message.reply_text(text, disable_web_page_preview=True)

@Client.on_message(filters.command("settings") & filters.private)
async def settings_panel(client, message):
    if not is_public_mode():
        return

    user_id = message.from_user.id

    await message.reply_text(
        "🛠 **Personal Settings Panel** 🛠\n\n"
        "Welcome to your personal settings.\n"
        "Here you can customize templates and thumbnails for your own files.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🖼 Manage Thumbnail", callback_data="user_thumb_menu")],
            [InlineKeyboardButton("📝 Edit Metadata Templates", callback_data="user_templates")],
            [InlineKeyboardButton("📝 Edit Filename Templates", callback_data="user_filename_templates")],
            [InlineKeyboardButton("📝 Edit Caption Template", callback_data="user_caption")],
            [InlineKeyboardButton("⚙️ General Settings", callback_data="user_general_settings")],
            [InlineKeyboardButton("👀 View Current Settings", callback_data="user_view")]
        ])
    )

@Client.on_callback_query(filters.regex(r"^(user_|edit_user_template_|edit_user_fn_template_)"))
async def user_settings_callback(client, callback_query):
    if not is_public_mode():
        return

    user_id = callback_query.from_user.id
    data = callback_query.data
    logger.info(f"User settings callback: {data} from user {user_id}")

    if data == "user_thumb_menu":
        await callback_query.message.edit_text(
            "🖼 **Manage Thumbnail**\n\n"
            "Select an action:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👀 View Current", callback_data="user_thumb_view")],
                [InlineKeyboardButton("📤 Set Thumbnail", callback_data="user_thumb_set")],
                [InlineKeyboardButton("🗑 Remove Thumbnail", callback_data="user_thumb_remove")],
                [InlineKeyboardButton("🔙 Back", callback_data="user_main")]
            ])
        )
    elif data == "user_thumb_view":
        thumb_bin, _ = await db.get_thumbnail(user_id)
        if thumb_bin:
            try:
                f = io.BytesIO(thumb_bin)
                f.name = "thumbnail.jpg"
                await client.send_photo(user_id, f, caption="**Your Current Default Thumbnail**")
                await callback_query.message.edit_text(
                    "🖼 **Manage Thumbnail**\n\n"
                    "Thumbnail sent above.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("👀 View Current", callback_data="user_thumb_view")],
                        [InlineKeyboardButton("📤 Set Thumbnail", callback_data="user_thumb_set")],
                        [InlineKeyboardButton("🗑 Remove Thumbnail", callback_data="user_thumb_remove")],
                        [InlineKeyboardButton("🔙 Back", callback_data="user_main")]
                    ])
                )
            except Exception as e:
                logger.error(f"Failed to send thumbnail: {e}")
                await callback_query.answer("Error sending thumbnail!", show_alert=True)
        else:
            await callback_query.answer("No thumbnail set!", show_alert=True)
    elif data == "user_thumb_set":
        user_sessions[user_id] = "awaiting_user_thumb"
        await callback_query.message.edit_text(
            "📤 **Set Default Thumbnail**\n\n"
            "Please send the **photo** you want to set as your default cover art/thumbnail.\n"
            "This will be embedded into your processed videos.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="user_thumb_menu")]])
        )
    elif data == "user_thumb_remove":
        await db.update_thumbnail(None, None, user_id)
        await callback_query.message.edit_text(
            "✅ **Thumbnail Removed**\n\nYour files will no longer use a default custom thumbnail.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="user_main")]])
        )
    elif data == "user_templates":
        await callback_query.message.edit_text(
            "📝 **Edit Metadata Templates**\n\n"
            "Select a field to edit:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Title", callback_data="edit_user_template_title"),
                 InlineKeyboardButton("Author", callback_data="edit_user_template_author")],
                [InlineKeyboardButton("Artist", callback_data="edit_user_template_artist"),
                 InlineKeyboardButton("Video", callback_data="edit_user_template_video")],
                [InlineKeyboardButton("Audio", callback_data="edit_user_template_audio"),
                 InlineKeyboardButton("Subtitle", callback_data="edit_user_template_subtitle")],
                [InlineKeyboardButton("🔙 Back", callback_data="user_main")]
            ])
        )
    elif data == "user_caption":
        templates = await db.get_all_templates(user_id)
        current_caption = templates.get("caption", "{random}")
        user_sessions[user_id] = "awaiting_user_template_caption"
        await callback_query.message.edit_text(
            "📝 **Edit Caption Template**\n\n"
            "Send the new caption text for your uploaded files.\n\n"
            f"Current: `{current_caption}`\n\n"
            "**Variables:**\n"
            "- `{filename}` : The final filename\n"
            "- `{size}` : File size (e.g. 1.5 GB)\n"
            "- `{duration}` : Video duration\n"
            "- `{random}` : Generates a random alphanumeric string (Anti-Hash)\n\n"
            "Send `{random}` to use the default random text generator.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="user_main")]])
        )
    elif data == "user_view":
        settings = await db.get_settings(user_id)
        templates = settings.get("templates", {}) if settings else {}
        has_thumb = "✅ Yes" if settings and settings.get("thumbnail_binary") else "❌ No"

        text = f"👀 **Your Current Settings**\n\n"
        text += f"**Thumbnail Set:** {has_thumb}\n\n"
        text += "**Metadata Templates:**\n"
        if templates:
            for k, v in templates.items():
                if k == "caption":
                    text += f"- **Caption:** `{v}`\n"
                else:
                    text += f"- **{k.capitalize()}:** `{v}`\n"
        else:
            text += "No templates set.\n"

        text += "\n**Filename Templates:**\n"
        fn_templates = settings.get("filename_templates", {}) if settings else {}
        if fn_templates:
            for k, v in fn_templates.items():
                text += f"- **{k.capitalize()}:** `{v}`\n"
        else:
            text += "No filename templates set.\n"

        text += f"\n**Channel Variable:** `{settings.get('channel', Config.DEFAULT_CHANNEL) if settings else Config.DEFAULT_CHANNEL}`\n"

        await callback_query.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="user_main")]])
        )
    elif data == "user_filename_templates":
        await callback_query.message.edit_text(
            "📝 **Edit Filename Templates**\n\n"
            "Select media type to edit:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Movies", callback_data="edit_user_fn_template_movies")],
                [InlineKeyboardButton("Series", callback_data="edit_user_fn_template_series")],
                [InlineKeyboardButton("Personal", callback_data="user_fn_templates_personal")],
                [InlineKeyboardButton("Subtitles", callback_data="user_fn_templates_subtitles")],
                [InlineKeyboardButton("🔙 Back", callback_data="user_main")]
            ])
        )
    elif data == "user_fn_templates_personal":
        await callback_query.message.edit_text(
            "📝 **Edit Personal Filename Templates**\n\n"
            "Select media type to edit:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Personal Files", callback_data="edit_user_fn_template_personal_file")],
                [InlineKeyboardButton("Personal Photos", callback_data="edit_user_fn_template_personal_photo")],
                [InlineKeyboardButton("Personal Videos", callback_data="edit_user_fn_template_personal_video")],
                [InlineKeyboardButton("🔙 Back", callback_data="user_filename_templates")]
            ])
        )
    elif data == "user_fn_templates_subtitles":
        await callback_query.message.edit_text(
            "📝 **Edit Subtitles Filename Templates**\n\n"
            "Select media type to edit:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Movies", callback_data="edit_user_fn_template_subtitles_movies")],
                [InlineKeyboardButton("Series", callback_data="edit_user_fn_template_subtitles_series")],
                [InlineKeyboardButton("🔙 Back", callback_data="user_filename_templates")]
            ])
        )
    elif data.startswith("edit_user_fn_template_"):
        field = data.replace("edit_user_fn_template_", "")
        user_sessions[user_id] = f"awaiting_user_fn_template_{field}"
        templates = await db.get_filename_templates(user_id)
        current_val = templates.get(field, "")
        await callback_query.message.edit_text(
            f"✏️ **Edit Filename Template ({field.capitalize()})**\n\n"
            f"Send the new template text.\n"
            f"Current: `{current_val}`\n\n"
            f"Variables: `{{Title}}`, `{{Year}}`, `{{Quality}}`, `{{Season}}`, `{{Episode}}`, `{{Season_Episode}}`, `{{Language}}`, `{{Channel}}`\n"
            f"Note: File extension will be added automatically, do not include it in the template.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="user_filename_templates")]])
        )
    elif data == "user_general_settings":
        current_channel = await db.get_channel(user_id)
        user_sessions[user_id] = "awaiting_user_channel"
        await callback_query.message.edit_text(
            "⚙️ **General Settings**\n\n"
            f"Send the new Channel name variable to use in templates (e.g. `@MyChannel`).\n"
            f"Current: `{current_channel}`\n\n",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="user_main")]])
        )
    elif data == "user_main" or data == "user_cancel":
        user_sessions.pop(user_id, None)
        await callback_query.message.edit_text(
            "🛠 **Personal Settings Panel** 🛠\n\n"
            "Welcome to your personal settings.\n"
            "Here you can customize templates and thumbnails for your own files.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🖼 Manage Thumbnail", callback_data="user_thumb_menu")],
                [InlineKeyboardButton("📝 Edit Metadata Templates", callback_data="user_templates")],
                [InlineKeyboardButton("📝 Edit Filename Templates", callback_data="user_filename_templates")],
                [InlineKeyboardButton("📝 Edit Caption Template", callback_data="user_caption")],
                [InlineKeyboardButton("⚙️ General Settings", callback_data="user_general_settings")],
                [InlineKeyboardButton("👀 View Current Settings", callback_data="user_view")]
            ])
        )
    elif data.startswith("edit_user_template_"):
        field = data.split("_")[-1]
        user_sessions[user_id] = f"awaiting_user_template_{field}"
        templates = await db.get_all_templates(user_id)
        current_val = templates.get(field, "")
        await callback_query.message.edit_text(
            f"✏️ **Edit {field.capitalize()} Template**\n\n"
            f"Send the new template text.\n"
            f"Current: `{current_val}`\n\n"
            f"Variables: `{{title}}`, `{{season_episode}}`, `{{lang}}` (for audio/subtitle)",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="user_templates")]])
        )

@Client.on_message(filters.photo & filters.private)
async def handle_user_photo(client, message):
    if not is_public_mode():
        return

    user_id = message.from_user.id
    if user_sessions.get(user_id) != "awaiting_user_thumb":
        # Pass to admin photo handler if applicable or to upload process
        return

    msg = await message.reply_text("Processing thumbnail...")
    try:
        file_id = message.photo.file_id
        path = await client.download_media(message, file_name=f"downloads/{user_id}_thumb.jpg")
        with open(path, "rb") as f:
            binary_data = f.read()
        await db.update_thumbnail(file_id, binary_data, user_id)
        await msg.edit_text("✅ Personal thumbnail updated successfully!",
                            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="user_thumb_menu")]]))
        user_sessions.pop(user_id, None)
    except Exception as e:
        logger.error(f"Thumbnail upload failed: {e}")
        await msg.edit_text(f"❌ Error: {e}")

@Client.on_message(filters.text & filters.private & ~filters.regex(r"^/"))
async def handle_user_text(client, message):
    if not is_public_mode():
        return

    user_id = message.from_user.id
    state = user_sessions.get(user_id)
    if not state:
        return

    if state.startswith("awaiting_user_template_"):
        field = state.split("_")[-1]
        new_template = message.text
        await db.update_template(field, new_template, user_id)

        if field == "caption":
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="user_main")]])
        else:
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Templates", callback_data="user_templates")]])

        await message.reply_text(f"✅ Your template for **{field.capitalize()}** updated to:\n`{new_template}`",
                                 reply_markup=reply_markup)
        user_sessions.pop(user_id, None)

    elif state.startswith("awaiting_user_fn_template_"):
        field = state.replace("awaiting_user_fn_template_", "")
        new_template = message.text
        await db.update_filename_template(field, new_template, user_id)

        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Filename Templates", callback_data="user_filename_templates")]])
        await message.reply_text(f"✅ Your filename template for **{field.capitalize()}** updated to:\n`{new_template}`",
                                 reply_markup=reply_markup)
        user_sessions.pop(user_id, None)

    elif state == "awaiting_user_channel":
        new_channel = message.text
        await db.update_channel(new_channel, user_id)

        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="user_main")]])
        await message.reply_text(f"✅ Your channel variable updated to:\n`{new_channel}`",
                                 reply_markup=reply_markup)
        user_sessions.pop(user_id, None)
