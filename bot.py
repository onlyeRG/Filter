import asyncio
import re
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from motor.motor_asyncio import AsyncIOMotorClient
from config import CONFIG

# ─── MongoDB ──────────────────────────────────────
mongo = AsyncIOMotorClient(CONFIG.MONGO_URL)
db = mongo[CONFIG.DB_NAME]
filters_col = db.filters

# ─── Bot ──────────────────────────────────────────
app = Client(
    "filter_bot",
    api_id=CONFIG.API_ID,
    api_hash=CONFIG.API_HASH,
    bot_token=CONFIG.BOT_TOKEN
)

# ─── Button Parser ─────────────────────────────────
BUTTON_REGEX = re.compile(r"\[(.*?)\]\(buttonurl:\/\/(.*?)\)")

def parse_text(text):
    match = BUTTON_REGEX.search(text)
    if not match:
        return text, None

    btn = InlineKeyboardMarkup(
        [[InlineKeyboardButton(match.group(1), url=match.group(2))]]
    )
    clean = BUTTON_REGEX.sub("", text).strip()
    return clean, btn

# ─── Commands ──────────────────────────────────────

@app.on_message(filters.command("start") & filters.private)
async def start(_, m: Message):
    await m.reply("Filter bot running.")

@app.on_message(filters.command("import") & filters.private & filters.user(CONFIG.OWNER_ID))
async def import_filters(_, m: Message):
    import json
    with open("filters.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    await filters_col.delete_many({})
    docs = []

    for x in data:
        docs.append({
            "name": x["name"].lower().strip(),
            "text": x["text"]
        })

    await filters_col.insert_many(docs)
    await m.reply(f"Imported {len(docs)} filters")

@app.on_message(filters.command("list") & filters.group)
async def list_filters(_, m: Message):
    if m.chat.id not in CONFIG.ALLOWED_GROUPS:
        return

    names = [x["name"] async for x in filters_col.find({}, {"name": 1})]
    if not names:
        return await m.reply("No filters")

    msg = "\n".join(f"- {n}" for n in names)
    if len(msg) > 4000:
        msg = msg[:3900] + "\n..."

    await m.reply(msg)

# ─── MAIN FILTER LOGIC ─────────────────────────────

@app.on_message(filters.group & filters.text & ~filters.command([]))
async def apply_filter(_, m: Message):
    if m.chat.id not in CONFIG.ALLOWED_GROUPS:
        return

    text = m.text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()

    words = text.split()
    filters_db = await filters_col.find().to_list(None)

    exact = None
    matches = []

    for f in filters_db:
        fname = f["name"]

        # exact match
        if text == fname:
            exact = f
            break

        # word based match
        fname_words = fname.split()
        if all(w in words for w in fname_words):
            matches.append(f)

    if exact:
        await send_reply(m, exact)
        return

    if len(matches) == 1:
        await send_reply(m, matches[0])

# ─── Reply + Auto Delete ───────────────────────────

async def send_reply(m: Message, f):
    text, btn = parse_text(f["text"])

    reply = await m.reply(
        text,
        reply_markup=btn,
        disable_web_page_preview=True
    )

    await asyncio.sleep(CONFIG.AUTO_DELETE_TIME)

    try:
        await reply.delete()
        await m.delete()
    except:
        pass

# ─── Run ───────────────────────────────────────────

print("🤖 Filter Bot Started")
app.run()
