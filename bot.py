import asyncio
import re
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram.enums import ChatType
from motor.motor_asyncio import AsyncIOMotorClient
from config import CONFIG

# ─── MongoDB ────────────────────────────────────────────────
mongo = AsyncIOMotorClient(CONFIG.MONGO_URL)
db = mongo[CONFIG.DB_NAME]
filters_col = db.filters

# ─── Bot ────────────────────────────────────────────────────
app = Client(
    "filter_bot",
    api_id=CONFIG.API_ID,
    api_hash=CONFIG.API_HASH,
    bot_token=CONFIG.BOT_TOKEN
)

# ─── Utils ──────────────────────────────────────────────────

IGNORE_WORDS = {"hindi", "dub", "sub", "movie", "series"}

def normalize(text: str) -> list[str]:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    words = [w for w in text.split() if w not in IGNORE_WORDS]
    return words

def match_filter(message_words, filter_words):
    """
    Matching rules:
    - If filter has <=2 words → partial allowed
    - If filter has >=4 words → full match required
    """
    if len(filter_words) >= 4:
        return message_words == filter_words

    if len(filter_words) <= 2:
        return all(w in message_words for w in filter_words)

    return False

# ─── Commands ───────────────────────────────────────────────

@app.on_message(filters.command("start") & filters.private)
async def start(_, m):
    await m.reply("🤖 Filter Bot Active")

@app.on_message(filters.command("import") & filters.private & filters.user(CONFIG.OWNER_ID))
async def import_filters(_, m):
    import json
    with open(CONFIG.IMPORT_FILE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    await filters_col.delete_many({})
    for item in data:
        await filters_col.insert_one({
            "name": item["name"],
            "text": item["text"],
            "words": normalize(item["name"])
        })

    await m.reply(f"✅ Imported {len(data)} filters")

@app.on_message(filters.command("list") & filters.group)
async def list_filters(_, m):
    docs = await filters_col.find().to_list(None)
    names = [d["name"] for d in docs]
    text = "\n".join(names)[:4000]
    await m.reply(text or "No filters")

@app.on_message(filters.command("del") & filters.group & filters.user(CONFIG.OWNER_ID))
async def delete_filter(_, m):
    if len(m.command) < 2:
        return await m.reply("Usage: /del name")

    name = " ".join(m.command[1:]).lower()
    r = await filters_col.delete_one({"name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}})

    await m.reply("✅ Deleted" if r.deleted_count else "❌ Not found")

# ─── MAIN FILTER LOGIC ──────────────────────────────────────

@app.on_message(
    filters.group
    & filters.text
    & ~filters.command
)
async def apply_filter(_, m: Message):
    if m.chat.id not in CONFIG.ALLOWED_GROUPS:
        return
    if m.edit_date:
        return

    msg_words = normalize(m.text)
    if not msg_words:
        return

    matches = []

    async for f in filters_col.find():
        if match_filter(msg_words, f["words"]):
            matches.append(f)

    # ❌ If none OR more than one match → do nothing
    if len(matches) != 1:
        return

    f = matches[0]

    # Button parsing
    btn = None
    txt = f["text"]

    match = re.search(r"\[(.*?)\]\(buttonurl:\/\/(.*?)\)", txt)
    if match:
        btn = InlineKeyboardMarkup(
            [[InlineKeyboardButton(match.group(1), url=match.group(2))]]
        )
        txt = re.sub(r"\[.*?\]\(buttonurl:\/\/.*?\)", "", txt).strip()

    reply = await m.reply(
        txt,
        reply_markup=btn,
        disable_web_page_preview=True
    )

    await asyncio.sleep(CONFIG.AUTO_DELETE_TIME)

    try:
        await reply.delete()
        await m.delete()
    except:
        pass

# ─── RUN ────────────────────────────────────────────────────
print("🤖 Filter Bot Started")
app.run()
