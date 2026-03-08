from pyrogram import filters
from config import Config

from database import db
from pyrogram.errors import UserNotParticipant
from utils.log import get_logger

logger = get_logger("utils.auth")

def is_authorized(user_id):
    if Config.PUBLIC_MODE:
        return True
    return user_id == Config.CEO_ID or user_id in Config.ADMIN_IDS

def is_admin(user_id):
    return user_id == Config.CEO_ID

async def check_force_sub(client, user_id):
    """Check if the user is subscribed to the Force-Sub Channel in Public Mode."""
    if not Config.PUBLIC_MODE:
        return True

    if user_id == Config.CEO_ID or user_id in Config.ADMIN_IDS:
        return True

    config = await db.get_public_config()
    force_sub_channel = config.get("force_sub_channel")

    if not force_sub_channel:
        return True

    try:
        await client.get_chat_member(force_sub_channel, user_id)
        return True
    except UserNotParticipant:
        return False
    except Exception as e:
        logger.error(f"Error checking force sub for {user_id} in {force_sub_channel}: {e}")
        # If the bot is not admin in the channel, it might throw an error.
        # We assume they are not subscribed or we can't verify.
        return False

# Simply use `message` (which is the update object)
# Pyrogram filters pass (filter, client, update)
# `update` is Message or CallbackQuery
# Both have `.from_user`
auth_filter = filters.create(lambda _, __, update: is_authorized(update.from_user.id if update.from_user else 0))
admin_filter = filters.create(lambda _, __, update: is_admin(update.from_user.id if update.from_user else 0))
