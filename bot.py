import json
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient
from config import *

# ---------- MongoDB ----------
mongo = MongoClient(MONGO_URL)
db = mongo[DB_NAME]
filters_db = db.filters

# ---------- Bot ----------
app = Client(
    "filter-bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ---------- Utils ----------
async def auto_delete(msg, delay=AUTO_DELETE_TIME):
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except:
        pass

def owner_only(message):
    return message.from_user and message.from_user.id == OWNER_ID

# ---------- IMPORT (PM ONLY, OWNER ONLY) ----------
@app.on_message(filters.private & filters.command("import"))
async def import_filters(client, message):
    if not owner_only(message):
        return await message.reply("❌ Owner only.")

    if not message.reply_to_message or not message.reply_to_message.document:
        return await message.reply("📎 Reply to a JSON file.")

    path = await message.reply_to_message.download()

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        added = 0
        for item in data:
            name = item.get("name")
            url = item.get("url")
            button_text = item.get("button_text", "⛩️ GET ANIME ⛩️")

            if not name or not url:
                continue

            doc = {
                "name": name.strip().lower(),
                "display": name.strip(),
                "url": url.strip(),
                "button_text": button_text.strip()
            }

            filters_db.update_one(
                {"name": doc["name"]},
                {"$set": doc},
                upsert=True
            )
            added += 1

        await message.reply(f"✅ Imported {added} filters.")

    except Exception as e:
        await message.reply(f"❌ Import failed:\n`{e}`")

# ---------- DELETE (PM ONLY, OWNER ONLY) ----------
@app.on_message(filters.private & filters.command("del"))
async def delete_filter(client, message):
    if not owner_only(message):
        return await message.reply("❌ Owner only.")

    if len(message.command) < 2:
        return await message.reply("Usage: /del <Anime Name>")

    name = " ".join(message.command[1:]).lower().strip()
    res = filters_db.delete_one({"name": name})

    if res.deleted_count:
        await message.reply(f"✅ Deleted `{name}`")
    else:
        await message.reply("❌ Not found.")

# ---------- LIST (PM ONLY, OWNER ONLY) ----------
# FIXED: chunk messages to avoid MESSAGE_TOO_LONG
@app.on_message(filters.private & filters.command("list"))
async def list_filters(client, message):
    if not owner_only(message):
        return

    data = list(filters_db.find({}, {"_id": 0, "display": 1}))
    if not data:
        return await message.reply("No filters found.")

    chunk = "📜 **Filters List**\n\n"
    for item in data:
        line = f"• {item.get('display','')}\n"
        if len(chunk) + len(line) > 4000:
            await message.reply(chunk)
            chunk = ""
        chunk += line

    if chunk:
        await message.reply(chunk)

# ---------- GROUP HANDLER ----------
@app.on_message(filters.group & filters.chat(ALLOWED_GROUPS) & filters.text)
async def group_handler(client, message):
    key = message.text.strip().lower()
    doc = filters_db.find_one({"name": key})
    if not doc:
        return

    reply = await message.reply(
        f"{doc['display']}\n[⛩️GET ANIME⛩️]",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton(doc["button_text"], url=doc["url"])]]
        ),
        disable_web_page_preview=True
    )

    # auto delete both messages after delay
    asyncio.create_task(auto_delete(reply))
    asyncio.create_task(auto_delete(message))

@app.on_message(filters.group & filters.text)
async def test(client, message):
    await message.reply("BOT IS READING THIS GROUP ✅")

print("🤖 Filter Bot Running")
app.run()
