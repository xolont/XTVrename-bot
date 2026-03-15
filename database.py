from motor.motor_asyncio import AsyncIOMotorClient
from config import Config
from utils.log import get_logger
import ssl
import certifi

logger = get_logger("database")


class Database:
    def __init__(self):
        if not Config.MAIN_URI:
            logger.warning("MAIN_URI is not set in environment variables.")
            self.client = None
            self.db = None
            self.settings = None
        else:
            try:
                self.client = AsyncIOMotorClient(
                    Config.MAIN_URI, tlsCAFile=certifi.where()
                )
            except Exception as e:
                logger.warning(
                    f"Failed to connect with certifi, trying with tlsAllowInvalidCertificates=True: {e}"
                )
                self.client = AsyncIOMotorClient(
                    Config.MAIN_URI, tlsAllowInvalidCertificates=True
                )

            self.db = self.client[Config.DB_NAME]
            self.settings = self.db[Config.SETTINGS_COLLECTION]
            self.daily_stats = self.db["daily_stats"]

    def _get_doc_id(self, user_id=None):
        if Config.PUBLIC_MODE and user_id is not None:
            return f"user_{user_id}"
        return "global_settings"

    async def get_settings(self, user_id=None):
        if self.settings is None:
            return None

        doc_id = self._get_doc_id(user_id)
        try:
            doc = await self.settings.find_one({"_id": doc_id})
            if not doc:
                default_settings = {
                    "_id": doc_id,
                    "thumbnail_file_id": None,
                    "thumbnail_binary": None,
                    "templates": Config.DEFAULT_TEMPLATES,
                    "filename_templates": Config.DEFAULT_FILENAME_TEMPLATES,
                    "channel": Config.DEFAULT_CHANNEL,
                }
                await self.settings.insert_one(default_settings)
                return default_settings
            return doc
        except Exception as e:
            logger.error(f"Error fetching settings for {doc_id}: {e}")
            return None

    async def update_template(self, key, value, user_id=None):
        if self.settings is None:
            return
        doc_id = self._get_doc_id(user_id)
        try:
            await self.settings.update_one(
                {"_id": doc_id}, {"$set": {f"templates.{key}": value}}, upsert=True
            )
        except Exception as e:
            logger.error(f"Error updating template for {doc_id}: {e}")

    async def update_thumbnail(self, file_id, binary_data, user_id=None):
        if self.settings is None:
            return
        doc_id = self._get_doc_id(user_id)
        try:
            await self.settings.update_one(
                {"_id": doc_id},
                {
                    "$set": {
                        "thumbnail_file_id": file_id,
                        "thumbnail_binary": binary_data,
                    }
                },
                upsert=True,
            )
        except Exception as e:
            logger.error(f"Error updating thumbnail for {doc_id}: {e}")

    async def get_thumbnail(self, user_id=None):
        if self.settings is None:
            return None, None
        doc_id = self._get_doc_id(user_id)
        try:
            doc = await self.settings.find_one({"_id": doc_id})
            if doc:
                return doc.get("thumbnail_binary"), doc.get("thumbnail_file_id")
        except Exception as e:
            logger.error(f"Error fetching thumbnail for {doc_id}: {e}")
        return None, None

    async def get_all_templates(self, user_id=None):
        settings = await self.get_settings(user_id)
        if settings:
            return settings.get("templates", Config.DEFAULT_TEMPLATES)
        return Config.DEFAULT_TEMPLATES

    async def get_filename_templates(self, user_id=None):
        settings = await self.get_settings(user_id)
        if settings:
            return settings.get("filename_templates", Config.DEFAULT_FILENAME_TEMPLATES)
        return Config.DEFAULT_FILENAME_TEMPLATES

    async def update_filename_template(self, key, value, user_id=None):
        if self.settings is None:
            return
        doc_id = self._get_doc_id(user_id)
        try:
            await self.settings.update_one(
                {"_id": doc_id},
                {"$set": {f"filename_templates.{key}": value}},
                upsert=True,
            )
        except Exception as e:
            logger.error(f"Error updating filename template for {doc_id}: {e}")

    async def get_channel(self, user_id=None):
        settings = await self.get_settings(user_id)
        if settings:
            return settings.get("channel", Config.DEFAULT_CHANNEL)
        return Config.DEFAULT_CHANNEL

    async def update_channel(self, value, user_id=None):
        if self.settings is None:
            return
        doc_id = self._get_doc_id(user_id)
        try:
            await self.settings.update_one(
                {"_id": doc_id}, {"$set": {"channel": value}}, upsert=True
            )
        except Exception as e:
            logger.error(f"Error updating channel for {doc_id}: {e}")

    async def get_dumb_channels(self, user_id=None):
        settings = await self.get_settings(user_id)
        if settings:
            return settings.get("dumb_channels", {})
        return {}

    async def add_dumb_channel(
        self, channel_id, channel_name, invite_link=None, user_id=None
    ):
        if self.settings is None:
            return
        doc_id = self._get_doc_id(user_id)
        try:
            update_data = {f"dumb_channels.{channel_id}": channel_name}
            if invite_link:
                update_data[f"dumb_channel_links.{channel_id}"] = invite_link

            await self.settings.update_one(
                {"_id": doc_id}, {"$set": update_data}, upsert=True
            )
        except Exception as e:
            logger.error(f"Error adding dumb channel for {doc_id}: {e}")

    async def get_all_dumb_channel_links(self):
        if self.settings is None:
            return []
        links = set()
        async for doc in self.settings.find({"dumb_channel_links": {"$exists": True}}):
            for link in doc.get("dumb_channel_links", {}).values():
                if link:
                    links.add(link)
        return list(links)

    async def remove_dumb_channel(self, channel_id, user_id=None):
        if self.settings is None:
            return
        doc_id = self._get_doc_id(user_id)
        try:
            await self.settings.update_one(
                {"_id": doc_id},
                {"$unset": {f"dumb_channels.{channel_id}": ""}},
                upsert=True,
            )
            settings = await self.get_settings(user_id)
            if settings and settings.get("default_dumb_channel") == str(channel_id):
                await self.settings.update_one(
                    {"_id": doc_id},
                    {"$unset": {"default_dumb_channel": ""}},
                    upsert=True,
                )
        except Exception as e:
            logger.error(f"Error removing dumb channel for {doc_id}: {e}")

    async def get_default_dumb_channel(self, user_id=None):
        settings = await self.get_settings(user_id)
        if settings:
            return settings.get("default_dumb_channel")
        return None

    async def set_default_dumb_channel(self, channel_id, user_id=None):
        if self.settings is None:
            return
        doc_id = self._get_doc_id(user_id)
        try:
            await self.settings.update_one(
                {"_id": doc_id},
                {"$set": {"default_dumb_channel": str(channel_id)}},
                upsert=True,
            )
        except Exception as e:
            logger.error(f"Error setting default dumb channel for {doc_id}: {e}")

    async def get_dumb_channel_timeout(self):
        if self.settings is None:
            return 3600
        if Config.PUBLIC_MODE:
            config = await self.get_public_config()
            return config.get("dumb_channel_timeout", 3600)
        else:
            doc = await self.settings.find_one({"_id": "global_settings"})
            if doc:
                return doc.get("dumb_channel_timeout", 3600)
            return 3600

    async def update_dumb_channel_timeout(self, timeout_seconds: int):
        if self.settings is None:
            return
        try:
            if Config.PUBLIC_MODE:
                await self.update_public_config("dumb_channel_timeout", timeout_seconds)
            else:
                await self.settings.update_one(
                    {"_id": "global_settings"},
                    {"$set": {"dumb_channel_timeout": timeout_seconds}},
                    upsert=True,
                )
        except Exception as e:
            logger.error(f"Error updating dumb channel timeout: {e}")

    async def get_pro_session(self):
        if self.settings is None:
            return None
        doc = await self.settings.find_one({"_id": "xtv_pro_settings"})
        if doc:
            return {
                "session_string": doc.get("session_string"),
                "api_id": doc.get("api_id"),
                "api_hash": doc.get("api_hash"),
                "tunnel_id": doc.get("tunnel_id"),
                "tunnel_link": doc.get("tunnel_link"),
            }
        return None

    async def save_pro_tunnel(self, tunnel_id: int, tunnel_link: str):
        if self.settings is None:
            return
        await self.settings.update_one(
            {"_id": "xtv_pro_settings"},
            {"$set": {"tunnel_id": tunnel_id, "tunnel_link": tunnel_link}},
            upsert=True,
        )

    async def save_pro_session(
        self, session_string: str, api_id: int = None, api_hash: str = None
    ):
        if self.settings is None:
            return
        update_doc = {"session_string": session_string}
        if api_id and api_hash:
            update_doc["api_id"] = api_id
            update_doc["api_hash"] = api_hash

        await self.settings.update_one(
            {"_id": "xtv_pro_settings"}, {"$set": update_doc}, upsert=True
        )

    async def delete_pro_session(self):
        if self.settings is None:
            return
        await self.settings.delete_one({"_id": "xtv_pro_settings"})

    async def get_public_config(self):
        if self.settings is None:
            return {}
        try:
            doc = await self.settings.find_one({"_id": "public_mode_config"})
            if not doc:
                default_config = {
                    "_id": "public_mode_config",
                    "bot_name": "XTV Rename Bot",
                    "community_name": "Our Community",
                    "support_contact": "@davdxpx",
                    "force_sub_channel": None,
                    "force_sub_link": None,
                    "daily_egress_mb": 0,
                    "daily_file_count": 0,
                }
                await self.settings.insert_one(default_config)
                return default_config
            return doc
        except Exception as e:
            logger.error(f"Error fetching public config: {e}")
            return {}

    async def update_public_config(self, key, value):
        if self.settings is None:
            return
        try:
            await self.settings.update_one(
                {"_id": "public_mode_config"}, {"$set": {key: value}}, upsert=True
            )
        except Exception as e:
            logger.error(f"Error updating public config: {e}")

    async def get_user_usage(self, user_id: int) -> dict:
        if self.settings is None:
            return {}
        try:
            doc = await self.settings.find_one({"_id": f"user_{user_id}"})
            if not doc:
                return {}
            return doc.get("usage", {})
        except Exception as e:
            logger.error(f"Error fetching usage for user {user_id}: {e}")
            return {}

    async def check_daily_quota(self, user_id: int, file_size_bytes: int) -> tuple[bool, str, dict]:
        # Always allow CEO and Admins
        if user_id == Config.CEO_ID or user_id in Config.ADMIN_IDS:
            return True, "", {}

        if self.settings is None:
            return True, "", {}

        if not Config.PUBLIC_MODE:
            return True, "", {}

        config = await self.get_public_config()
        daily_egress_mb_limit = config.get("daily_egress_mb", 0)
        daily_file_count_limit = config.get("daily_file_count", 0)

        # No limits configured
        if daily_egress_mb_limit <= 0 and daily_file_count_limit <= 0:
            return True, "", {}

        import datetime
        current_utc_date = datetime.datetime.utcnow().strftime("%Y-%m-%d")

        try:
            doc = await self.settings.find_one({"_id": f"user_{user_id}"})

            # Use dictionary representation since MongoDB nested updates don't initialize the root automatically if using multiple paths
            usage = doc.get("usage", {}) if doc else {}

            # Reset daily usage if it's a new day
            if usage.get("date") != current_utc_date:
                usage["date"] = current_utc_date
                usage["egress_mb"] = 0.0
                usage["file_count"] = 0
                usage["quota_hits"] = 0

                # Make sure all-time fields exist
                if "egress_mb_alltime" not in usage:
                    usage["egress_mb_alltime"] = 0.0
                if "file_count_alltime" not in usage:
                    usage["file_count_alltime"] = 0

                await self.settings.update_one(
                    {"_id": f"user_{user_id}"},
                    {"$set": {"usage": usage}},
                    upsert=True
                )

            incoming_mb = file_size_bytes / (1024 * 1024)

            # Check limits
            if daily_file_count_limit > 0 and usage.get("file_count", 0) >= daily_file_count_limit:
                await self.record_quota_hit(user_id)
                return False, f"You've reached your daily {daily_file_count_limit} file limit.", usage

            if daily_egress_mb_limit > 0 and (usage.get("egress_mb", 0.0) + incoming_mb) > daily_egress_mb_limit:
                await self.record_quota_hit(user_id)
                mb_limit_str = f"{daily_egress_mb_limit} MB"
                if daily_egress_mb_limit >= 1024:
                    mb_limit_str = f"{daily_egress_mb_limit / 1024:.2f} GB"
                return False, f"You've reached your daily {mb_limit_str} egress limit.", usage

            return True, "", usage

        except Exception as e:
            logger.error(f"Error checking daily quota for {user_id}: {e}")
            return True, "", {}

    async def record_quota_hit(self, user_id: int):
        if self.settings is None:
            return

        import datetime
        current_utc_date = datetime.datetime.utcnow().strftime("%Y-%m-%d")

        try:
            # Increment user quota hit
            await self.settings.update_one(
                {"_id": f"user_{user_id}"},
                {"$inc": {"usage.quota_hits": 1}},
                upsert=True
            )

            # Increment global quota hit for the day
            await self.daily_stats.update_one(
                {"date": current_utc_date},
                {"$inc": {"quota_hits": 1}},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Error recording quota hit: {e}")

    async def update_usage(self, user_id: int, processed_file_size_bytes: int):
        if self.settings is None:
            return

        import datetime
        current_utc_date = datetime.datetime.utcnow().strftime("%Y-%m-%d")
        processed_mb = processed_file_size_bytes / (1024 * 1024)

        try:
            # Ensure the user has the current date set in case they bypassed check_daily_quota (e.g. CEO/Admins)
            user_doc = await self.settings.find_one({"_id": f"user_{user_id}"})
            usage = user_doc.get("usage", {}) if user_doc else {}

            if usage.get("date") != current_utc_date:
                await self.settings.update_one(
                    {"_id": f"user_{user_id}"},
                    {"$set": {
                        "usage.date": current_utc_date,
                        "usage.egress_mb": 0.0,
                        "usage.file_count": 0,
                        "usage.quota_hits": 0
                    }},
                    upsert=True
                )

            # Increment usage
            await self.settings.update_one(
                {"_id": f"user_{user_id}"},
                {"$inc": {
                    "usage.egress_mb": processed_mb,
                    "usage.file_count": 1,
                    "usage.egress_mb_alltime": processed_mb,
                    "usage.file_count_alltime": 1
                }},
                upsert=True
            )

            # Update daily stats globally
            await self.daily_stats.update_one(
                {"date": current_utc_date},
                {"$inc": {
                    "egress_mb": processed_mb,
                    "file_count": 1
                }},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Error updating usage: {e}")

    async def get_daily_stats(self, limit=7):
        if self.settings is None:
            return []
        try:
            cursor = self.daily_stats.find({}).sort("date", -1).limit(limit)
            return await cursor.to_list(length=limit)
        except Exception as e:
            logger.error(f"Error fetching daily stats: {e}")
            return []

    async def get_top_users_today(self, limit=10, skip=0):
        if self.settings is None:
            return [], 0

        import datetime
        current_utc_date = datetime.datetime.utcnow().strftime("%Y-%m-%d")

        try:
            query = {
                "_id": {"$regex": "^user_"},
                "usage.date": current_utc_date,
                "usage.egress_mb": {"$gt": 0}
            }

            cursor = self.settings.find(query).sort("usage.egress_mb", -1).skip(skip).limit(limit)
            users = await cursor.to_list(length=limit)
            total = await self.settings.count_documents(query)

            return users, total
        except Exception as e:
            logger.error(f"Error fetching top users: {e}")
            return [], 0

    async def get_total_users(self):
        if self.settings is None:
            return 0
        try:
            return await self.settings.count_documents({"_id": {"$regex": "^user_"}})
        except Exception as e:
            return 0

    async def get_dashboard_stats(self):
        if self.settings is None:
            return {}

        import datetime
        current_utc_date = datetime.datetime.utcnow().strftime("%Y-%m-%d")

        try:
            # Get today's global stats
            today_stats = await self.daily_stats.find_one({"date": current_utc_date}) or {}

            # Get all-time totals using aggregation
            all_time_pipeline = [
                {"$group": {
                    "_id": None,
                    "total_egress": {"$sum": "$egress_mb"},
                    "total_files": {"$sum": "$file_count"}
                }}
            ]
            all_time_result = await self.daily_stats.aggregate(all_time_pipeline).to_list(1)
            all_time = all_time_result[0] if all_time_result else {"total_egress": 0, "total_files": 0}

            # Count users
            total_users = await self.get_total_users()

            # Get blocked users count
            public_config = await self.get_public_config()
            blocked_users = len(public_config.get("blocked_users", []))

            # Get start date (first entry in daily_stats)
            first_stat = await self.daily_stats.find_one({}, sort=[("date", 1)])
            bot_start_date = first_stat["date"] if first_stat else current_utc_date

            return {
                "total_users": total_users,
                "files_today": today_stats.get("file_count", 0),
                "egress_today_mb": today_stats.get("egress_mb", 0.0),
                "quota_hits_today": today_stats.get("quota_hits", 0),
                "total_files": all_time.get("total_files", 0),
                "total_egress_mb": all_time.get("total_egress", 0.0),
                "blocked_users": blocked_users,
                "bot_start_date": bot_start_date
            }
        except Exception as e:
            logger.error(f"Error getting dashboard stats: {e}")
            return {}

    async def block_user(self, user_id: int):
        if self.settings is None:
            return
        try:
            await self.settings.update_one(
                {"_id": "public_mode_config"},
                {"$addToSet": {"blocked_users": user_id}},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Error blocking user: {e}")

    async def unblock_user(self, user_id: int):
        if self.settings is None:
            return
        try:
            await self.settings.update_one(
                {"_id": "public_mode_config"},
                {"$pull": {"blocked_users": user_id}}
            )
        except Exception as e:
            logger.error(f"Error unblocking user: {e}")

    async def is_user_blocked(self, user_id: int) -> bool:
        if self.settings is None:
            return False
        try:
            config = await self.get_public_config()
            return user_id in config.get("blocked_users", [])
        except Exception as e:
            return False

    async def reset_user_quota(self, user_id: int):
        if self.settings is None:
            return
        try:
            await self.settings.update_one(
                {"_id": f"user_{user_id}"},
                {"$set": {
                    "usage.egress_mb": 0.0,
                    "usage.file_count": 0,
                    "usage.quota_hits": 0
                }}
            )
        except Exception as e:
            logger.error(f"Error resetting user quota: {e}")

    async def get_all_users(self):
        if self.settings is None:
            return []
        users = []
        try:
            async for doc in self.settings.find({"_id": {"$regex": "^user_"}}):
                user_id_str = str(doc["_id"]).replace("user_", "")
                if user_id_str.isdigit():
                    users.append(int(user_id_str))
        except Exception as e:
            logger.error(f"Error fetching all users: {e}")
        return users


db = Database()

# --------------------------------------------------------------------------
# Developed by 𝕏0L0™ (@davdxpx) | © 2026 XTV Network Global
# Don't Remove Credit
# Telegram Channel @XTVbots
# Developed for the 𝕏TV Network @XTVglobal
# Backup Channel @XTVhome
# Contact on Telegram @davdxpx
# --------------------------------------------------------------------------
