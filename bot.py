import asyncio
import json
import re
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from motor.motor_asyncio import AsyncIOMotorClient
from config import *

# -------------------- DB --------------------
mongo = AsyncIOMotorClient(MONGO_URL)
db = mongo[DB_NAME]
col = db.filters

# -------------------- BOT --------------------
app = Client(
    "filter-bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# -------------------- HELPERS --------------------

def normalize(text: str) -> str:
    """lowercase + remove symbols"""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()

def build_keyboard(text: str):
    match = re.search(r"\[(.*?)\]\(buttonurl://(.*?)\)", text)
    if not match:
        return text, None

    btn_text = match.group(1)
    btn_url = match.group(2)
    clean = re.sub(r"\[(.*?)\]\(buttonurl://(.*?)\)", "", text).strip()

    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton(btn_text, url=btn_url)]]
    )
    return clean, kb

# -------------------- COMMANDS --------------------

@app.on_message(filters.private & filters.command("start"))
async def start(_, m: Message):
    await m.reply_text("✅ Filter Bot is running")

@app.on_message(filters.private & filters.command("import") & filters.user(OWNER_ID))
async def import_filters(_, m: Message):
    try:
        with open("filters.json", "r", encoding="utf-8") as f:
            data = json.load(f)

        await col.delete_many({})
        docs = []

        for i in data:
            name = normalize(i["name"])
            words = name.split()

            docs.append({
                "name": name,
                "words": words,
                "word_count": len(words),
                "text": i["text"]
            })

        if docs:
            await col.insert_many(docs)
            await m.reply_text(f"✅ Imported {len(docs)} filters")
        else:
            await m.reply_text("❌ No valid filters")

    except Exception as e:
        await m.reply_text(str(e))

@app.on_message(filters.group & filters.command("list"))
async def list_filters(_, m: Message):
    items = await col.find().to_list(None)
    if not items:
        return await m.reply_text("No filters")

    text = "\n".join(f"- {i['name']}" for i in items)
    await m.reply_text(text[:4000])

@app.on_message(filters.group & filters.command("del") & filters.user(OWNER_ID))
async def del_filter(_, m: Message):
    if len(m.command) < 2:
        return await m.reply_text("/del <name>")

    name = normalize(" ".join(m.command[1:]))
    r = await col.delete_one({"name": name})

    if r.deleted_count:
        await m.reply_text("✅ Deleted")
    else:
        await m.reply_text("❌ Not found")

# -------------------- FILTER LOGIC --------------------

@app.on_message(filters.group & filters.text & ~filters.regex(r"^/"))
async def apply_filter(_, m: Message):
    text = normalize(m.text)
    words = text.split()

    filters_db = await col.find().to_list(None)
    matches = []

    for f in filters_db:
        # Rule:
        # 1 word filter → trigger if word present
        # 2 words → first word enough
        # 3+ words → full phrase required
        if f["word_count"] == 1:
            if f["words"][0] in words:
                matches.append(f)

        elif f["word_count"] == 2:
            if f["words"][0] in words:
                matches.append(f)

        else:
            if f["name"] in text:
                matches.append(f)

    # If multiple matches → do nothing
    if len(matches) != 1:
        return

    target = matches[0]
    clean, kb = build_keyboard(target["text"])

    reply = await m.reply_text(
        clean,
        reply_markup=kb,
        disable_web_page_preview=True
    )

    # Auto delete
    await asyncio.sleep(AUTO_DELETE_TIME)
    try:
        await reply.delete()
        await m.delete()
    except:
        pass

# -------------------- RUN --------------------
print("🤖 Filter Bot Started")
app.run()
