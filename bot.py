import asyncio
import json
import re
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from motor.motor_asyncio import AsyncIOMotorClient
from config import CONFIG

app = Client(
    "filterbot",
    api_id=CONFIG.API_ID,
    api_hash=CONFIG.API_HASH,
    bot_token=CONFIG.BOT_TOKEN
)

mongo = AsyncIOMotorClient(CONFIG.MONGO_URL)
db = mongo[CONFIG.DB_NAME]
filters_col = db.filters

BUTTON_REGEX = re.compile(r"\[(.*?)\]\(buttonurl:\/\/(.*?)\)")

def parse_buttons(text):
    match = BUTTON_REGEX.search(text)
    if not match:
        return text, None

    btn_text, btn_url = match.groups()
    clean = BUTTON_REGEX.sub("", text).strip()

    return clean, InlineKeyboardMarkup(
        [[InlineKeyboardButton(btn_text, url=btn_url)]]
    )

async def send_reply(msg, data):
    text, keyboard = parse_buttons(data["text"])
    reply = await msg.reply_text(
        text,
        reply_markup=keyboard,
        disable_web_page_preview=True
    )

    await asyncio.sleep(CONFIG.AUTO_DELETE_TIME)
    try:
        await reply.delete()
        await msg.delete()
    except:
        pass

# ---------------- START ----------------

@app.on_message(filters.command("start") & filters.private)
async def start(_, msg):
    await msg.reply("✅ Filter bot running")

# ---------------- IMPORT ----------------

@app.on_message(filters.command("import") & filters.private & filters.user(CONFIG.OWNER_ID))
async def import_filters(_, msg):
    with open(CONFIG.IMPORT_FILE_PATH, encoding="utf-8") as f:
        data = json.load(f)

    await filters_col.delete_many({})

    bulk = []
    for item in data:
        name = item["name"].lower().strip()
        words = name.split()

        if len(words) >= 5:
            match_type = "long"
            keywords = name
        elif len(words) >= 3:
            match_type = "medium"
            keywords = " ".join(words[:4])
        else:
            match_type = "short"
            keywords = words

        bulk.append({
            "name": name,
            "keywords": keywords,
            "match_type": match_type,
            "text": item["text"]
        })

    if bulk:
        await filters_col.insert_many(bulk)

    await msg.reply(f"✅ Imported {len(bulk)} filters")

# ---------------- LIST ----------------

@app.on_message(filters.command("list") & filters.group)
async def list_filters(_, msg):
    if msg.chat.id not in CONFIG.ALLOWED_GROUPS:
        return

    cursor = filters_col.find({}, {"name": 1}).sort("name", 1)
    names = [f["name"] async for f in cursor]

    if not names:
        return await msg.reply("No filters")

    text = "📜 **Filters List**\n\n"
    for n in names:
        if len(text) > 3800:
            await msg.reply(text)
            text = ""
        text += f"• `{n}`\n"

    if text:
        await msg.reply(text)

# ---------------- DELETE ----------------

@app.on_message(filters.command("del") & filters.group & filters.user(CONFIG.OWNER_ID))
async def delete_filter(_, msg):
    if msg.chat.id not in CONFIG.ALLOWED_GROUPS:
        return

    if len(msg.command) < 2:
        return await msg.reply("Usage: /del <name>")

    name = " ".join(msg.command[1:]).lower()
    res = await filters_col.delete_one({"name": name})

    if res.deleted_count:
        await msg.reply("✅ Deleted")
    else:
        await msg.reply("❌ Not found")

# ---------------- FILTER LOGIC ----------------

@app.on_message(filters.group & filters.text & ~filters.command([]))
async def apply_filters(_, msg: Message):
    if msg.chat.id not in CONFIG.ALLOWED_GROUPS:
        return

    text = msg.text.lower().strip()
    words = re.findall(r"\w+", text)

    # 1️⃣ LONG (5+ words) → exact phrase
    doc = await filters_col.find_one({
        "match_type": "long",
        "keywords": {"$regex": re.escape(text)}
    })
    if doc:
        return await send_reply(msg, doc)

    # 2️⃣ MEDIUM (3–4 words) → prefix match
    for i in (4, 3):
        if len(words) >= i:
            phrase = " ".join(words[:i])
            doc = await filters_col.find_one({
                "match_type": "medium",
                "keywords": phrase
            })
            if doc:
                return await send_reply(msg, doc)

    # 3️⃣ SHORT (1–2 words) → word match ONLY if no long/medium hit
    doc = await filters_col.find_one({
        "match_type": "short",
        "keywords": {"$in": words}
    })
    if doc:
        return await send_reply(msg, doc)

print("🤖 Filter Bot Running")
app.run()
