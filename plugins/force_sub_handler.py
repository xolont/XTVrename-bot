from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus
from database import db
from plugins.admin import admin_sessions, is_admin
from config import Config
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.log import get_logger

logger = get_logger("plugins.force_sub_handler")

@Client.on_chat_member_updated(filters.channel)
async def handle_bot_added_to_channel(client, update):
    if not Config.PUBLIC_MODE:
        return

    user_id = update.from_user.id

    # Check if the person who added the bot is the CEO and in the setup state
    if not is_admin(user_id):
        return

    state = admin_sessions.get(user_id)
    if state != "awaiting_public_force_sub":
        return

    # Check if the bot was actually promoted/added as an admin
    new_status = update.new_chat_member.status if update.new_chat_member else None

    if new_status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
        chat_id = update.chat.id
        chat_title = update.chat.title

        try:
            # Try to get or create invite link
            chat_info = await client.get_chat(chat_id)
            invite_link = chat_info.invite_link
            if not invite_link:
                invite_link = await client.export_chat_invite_link(chat_id)

            await db.update_public_config("force_sub_channel", chat_id)
            await db.update_public_config("force_sub_link", invite_link)

            # Notify the CEO in their private chat
            await client.send_message(
                chat_id=user_id,
                text=f"✅ **Force-Sub Setup Complete!**\n\nI successfully detected that you added me to **{chat_title}**.\n\nChannel ID: `{chat_id}`\nSaved Link: {invite_link}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="admin_main")]])
            )

            # Clear the session state
            admin_sessions.pop(user_id, None)

        except Exception as e:
            logger.error(f"Force sub setup error during chat_member_updated: {e}")
            await client.send_message(
                chat_id=user_id,
                text=f"❌ **Failed to verify channel.**\n\nI was added to the channel, but I don't have permission to create invite links. Please grant me the 'Invite Users via Link' permission.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_main")]])
            )
