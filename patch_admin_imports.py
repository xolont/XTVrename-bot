with open("plugins/admin.py", "r") as f:
    content = f.read()

import_pattern = "from pyrogram import Client, filters"
import_replace = "from pyrogram import Client, filters\nfrom pyrogram.types import CallbackQuery, Message"
content = content.replace(import_pattern, import_replace)

with open("plugins/admin.py", "w") as f:
    f.write(content)
