import asyncio
import json
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pymongo import MongoClient
from config import *

# ------------------ APP ------------------
app = Client(
    "filter-bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ------------------ DB ------------------
mongo = MongoClient(MONGO_URL)
db = mongo[DB_NAME]
filters_collection = db.filters

# ------------------ UTILS ------------------
async def auto_delete(msg):
    await asyncio.sleep(AUTO_DELETE_TIME)
    try:
        await msg.delete()
    except:
        pass


def split_text(text, limit=4000):
    return [text[i:i + limit] for i in range(0, len(text), limit)]


def build_buttons(data):
    if "buttons" not in data:
        return None

    rows = []
    for btn in data["buttons"]:
        rows.append([
            InlineKeyboardButton(
                btn["text"],
                url=btn["url"]
            )
        ])
    return InlineKeyboardMarkup(rows)


# ------------------ IMPORT (OWNER ONLY, PM) ------------------
@app.on_message(filters.private & filters.document & filters.user(OWNER_ID))
async def import_filters(client, message):
    file_path = await message.download()
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    added = 0
    for item in data:
        item["name"] = item["name"].strip().lower()
        filters_collection.update_one(
            {
                "chat_id": item["chat_id"],
                "name": item["name"]
            },
            {"$set": item},
            upsert=True
        )
        added += 1

    await message.reply_text(f"✅ Imported {added} filters")


# ------------------ LIST ------------------
@app.on_message(filters.command("list") & filters.group)
async def list_filters(client, message):
    if message.chat.id not in ALLOWED_GROUPS:
        return

    data = filters_collection.find({"chat_id": message.chat.id})
    names = [f"• {x['name'].title()}" for x in data]

    if not names:
        await message.reply("No filters found.")
        return

    text = "📜 **Filters List**\n\n" + "\n".join(names)
    for part in split_text(text):
        await message.reply(part)


# ------------------ DELETE ------------------
@app.on_message(filters.command("del") & filters.group & filters.user(OWNER_ID))
async def delete_filter(client, message):
    if message.chat.id not in ALLOWED_GROUPS:
        return

    if len(message.command) < 2:
        await message.reply("Usage: /del <name>")
        return

    name = " ".join(message.command[1:]).lower()
    res = filters_collection.delete_one({
        "chat_id": message.chat.id,
        "name": name
    })

    if res.deleted_count:
        await message.reply(f"❌ Deleted: {name.title()}")
    else:
        await message.reply("Filter not found.")


# ------------------ FILTER LISTENER ------------------
@app.on_message(filters.group & filters.text & ~filters.command)
async def filter_listener(client, message):
    chat_id = message.chat.id

    if chat_id not in ALLOWED_GROUPS:
        return

    text = message.text.strip().lower()

    data = filters_collection.find_one({
        "chat_id": chat_id,
        "name": text
    })

    if not data:
        return

    buttons = build_buttons(data)

    reply = await message.reply_text(
        data["text"],
        reply_markup=buttons,
        disable_web_page_preview=True
    )

    asyncio.create_task(auto_delete(reply))
    asyncio.create_task(auto_delete(message))


# ------------------ START ------------------
print("🤖 Filter Bot Running")
app.run()
