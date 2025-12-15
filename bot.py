import json
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient
from config import *

# ---------------- MONGO ----------------
mongo = MongoClient(MONGO_URL)
db = mongo[DB_NAME]
filters_db = db.filters

# ---------------- BOT ----------------
app = Client(
    "filter-bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ---------------- UTIL ----------------
async def auto_delete(msg, delay=AUTO_DELETE_TIME):
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except:
        pass

# ---------------- IMPORT ----------------
@app.on_message(filters.private & filters.command("import"))
async def import_filters(client, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("❌ Owner only.")

    if not message.reply_to_message or not message.reply_to_message.document:
        return await message.reply("📎 Reply to JSON file.")

    path = await message.reply_to_message.download()

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        added = 0
        for item in data:
            filters_db.update_one(
                {"name": item["name"].lower()},
                {"$set": item},
                upsert=True
            )
            added += 1

        await message.reply(f"✅ Imported {added} filters.")

    except Exception as e:
        await message.reply(f"❌ Error:\n`{e}`")

# ---------------- DELETE ----------------
@app.on_message(filters.private & filters.command("del"))
async def delete_filter(client, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("❌ Owner only.")

    if len(message.command) < 2:
        return await message.reply("Usage: /del Anime Name")

    name = " ".join(message.command[1:]).lower()
    result = filters_db.delete_one({"name": name})

    if result.deleted_count:
        await message.reply(f"✅ Deleted `{name}`")
    else:
        await message.reply("❌ Not found")

# ---------------- LIST ----------------
@app.on_message(filters.private & filters.command("list"))
async def list_filters(client, message):
    if message.from_user.id != OWNER_ID:
        return

    data = list(filters_db.find())
    if not data:
        return await message.reply("No filters found.")

    text = "📜 **Filters List**\n\n"
    for i in data:
        text += f"• {i['name']}\n"

    await message.reply(text)

# ---------------- GROUP HANDLER ----------------
@app.on_message(filters.group & filters.chat(ALLOWED_GROUPS) & filters.text)
async def group_handler(client, message):
    key = message.text.strip().lower()

    data = filters_db.find_one({"name": key})
    if not data:
        return

    reply = await message.reply(
        f"{data['name']}\n[⛩️GET ANIME⛩️]",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton(data["button_text"], url=data["url"])]]
        ),
        disable_web_page_preview=True
    )

    asyncio.create_task(auto_delete(reply))
    asyncio.create_task(auto_delete(message))

print("🤖 Filter Bot Running")
app.run()
