import asyncio
import json
import re
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from motor.motor_asyncio import AsyncIOMotorClient
from config import CONFIG

# ---------- BOT ----------
app = Client(
    "filter-bot",
    api_id=CONFIG.API_ID,
    api_hash=CONFIG.API_HASH,
    bot_token=CONFIG.BOT_TOKEN
)

# ---------- DATABASE ----------
mongo = AsyncIOMotorClient(CONFIG.MONGO_URL)
db = mongo[CONFIG.DB_NAME]
filters_col = db.filters

# ---------- BUTTON PARSER ----------
BTN_REGEX = re.compile(r"\[(.*?)\]\(buttonurl:\/\/(.*?)\)")

def parse_text(text):
    match = BTN_REGEX.search(text)
    if not match:
        return text, None
    btn_text, btn_url = match.groups()
    clean = BTN_REGEX.sub("", text).strip()
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton(btn_text, url=btn_url)]]
    )
    return clean, keyboard

# ---------- START ----------
@app.on_message(filters.command("start") & filters.private)
async def start(_, m):
    await m.reply("✅ Filter Bot Running")

# ---------- IMPORT ----------
@app.on_message(filters.command("import") & filters.private & filters.user(CONFIG.OWNER_ID))
async def import_filters(_, m):
    with open(CONFIG.IMPORT_FILE_PATH, encoding="utf-8") as f:
        data = json.load(f)

    await filters_col.delete_many({})

    docs = []
    for i in data:
        name = i["name"].lower().strip()
        name = re.sub(r"[^\w\s]", "", name)
        docs.append({
            "name": name,
            "text": i["text"]
        })

    if docs:
        await filters_col.insert_many(docs)
        await m.reply(f"✅ Imported {len(docs)} filters")
    else:
        await m.reply("❌ No filters found")

# ---------- LIST ----------
@app.on_message(filters.command("list") & filters.group)
async def list_filters(_, m):
    if m.chat.id not in CONFIG.ALLOWED_GROUPS:
        return

    items = await filters_col.find().sort("name", 1).to_list(None)
    if not items:
        return await m.reply("No filters")

    text = "**📜 Filters List:**\n\n"
    for f in items:
        text += f"• {f['name']}\n"

    for i in range(0, len(text), 4000):
        await m.reply(text[i:i+4000])

# ---------- DELETE ----------
@app.on_message(filters.command("del") & filters.group & filters.user(CONFIG.OWNER_ID))
async def delete_filter(_, m):
    if len(m.command) < 2:
        return await m.reply("/del <name>")

    name = " ".join(m.command[1:]).lower()
    name = re.sub(r"[^\w\s]", "", name)

    res = await filters_col.delete_one({"name": name})
    if res.deleted_count:
        await m.reply("✅ Deleted")
    else:
        await m.reply("❌ Not found")

# ---------- SEND ----------
async def send_reply(msg, f):
    text, markup = parse_text(f["text"])
    reply = await msg.reply_text(text, reply_markup=markup, disable_web_page_preview=True)

    await asyncio.sleep(CONFIG.AUTO_DELETE_TIME)
    try:
        await reply.delete()
        await msg.delete()
    except:
        pass

# ---------- CORE FILTER LOGIC ----------
@app.on_message(filters.group & filters.text & ~filters.command([]))
async def apply_filters(_, msg: Message):
    if msg.chat.id not in CONFIG.ALLOWED_GROUPS:
        return

    text = msg.text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    words = text.split()

    filters_list = await filters_col.find().to_list(None)

    # 4+ words → first 4 exact
    if len(words) >= 4:
        key = " ".join(words[:4])
        for f in filters_list:
            fw = f["name"].split()
            if len(fw) >= 4 and " ".join(fw[:4]) == key:
                return await send_reply(msg, f)

    # 3 words → first 2
    if len(words) >= 2:
        key = " ".join(words[:2])
        for f in filters_list:
            fw = f["name"].split()
            if len(fw) == 3 and " ".join(fw[:2]) == key:
                return await send_reply(msg, f)

    # 2 words → first word
    key = words[0]
    for f in filters_list:
        fw = f["name"].split()
        if len(fw) == 2 and fw[0] == key:
            return await send_reply(msg, f)

    # 1 word
    for f in filters_list:
        if f["name"] == key:
            return await send_reply(msg, f)

# ---------- RUN ----------
print("🤖 Filter Bot Started")
app.run()
