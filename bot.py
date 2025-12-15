import json
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import *

app = Client(
    "filter-bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

FILTERS = {}  # { "anime": {"text": str, "button": InlineKeyboardMarkup} }

# -------------------------
# IMPORT (PM ONLY, OWNER ONLY)
# -------------------------
@app.on_message(filters.private & filters.command("import"))
async def import_filters(client, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("❌ Only owner can import filters.")

    if not message.reply_to_message or not message.reply_to_message.document:
        return await message.reply("📎 Reply to a JSON file.")

    file_path = await message.reply_to_message.download()

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        FILTERS.clear()
        count = 0

        for item in data:
            name = item["name"].strip()
            url = item["url"].strip()

            FILTERS[name.lower()] = {
                "text": f"{name}\n[⛩️GET ANIME⛩️]",
                "button": InlineKeyboardMarkup(
                    [[InlineKeyboardButton("⛩️ GET ANIME ⛩️", url=url)]]
                )
            }
            count += 1

        await message.reply(f"✅ Imported {count} filters successfully.")

    except Exception as e:
        await message.reply(f"❌ Import failed:\n`{e}`")

# -------------------------
# GROUP FILTER HANDLER
# -------------------------
@app.on_message(filters.group & filters.chat(WORK_GROUP_ID) & filters.text)
async def group_filter(client, message):
    key = message.text.strip().lower()

    if key in FILTERS:
        data = FILTERS[key]

        sent = await message.reply(
            data["text"],
            reply_markup=data["button"],
            disable_web_page_preview=True
        )

        await asyncio.sleep(AUTO_DELETE_TIME)

        try:
            await sent.delete()
            await message.delete()
        except:
            pass

print("🤖 Filter Bot Started")
app.run()
