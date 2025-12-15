import asyncio
import re
import aiohttp
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from motor.motor_asyncio import AsyncIOMotorClient
from config import CONFIG

# ─── DATABASE ─────────────────────────────────────
mongo = AsyncIOMotorClient(CONFIG.MONGO_URL)
db = mongo[CONFIG.DB_NAME]
filters_col = db.filters

# ─── BOT INIT ─────────────────────────────────────
app = Client(
    "filter_bot",
    api_id=CONFIG.API_ID,
    api_hash=CONFIG.API_HASH,
    bot_token=CONFIG.BOT_TOKEN
)

# ─── TMDB ─────────────────────────────────────────
TMDB_SEARCH_URL = "https://api.themoviedb.org/3/search/multi"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"

async def fetch_tmdb(query: str):
    params = {
        "api_key": CONFIG.TMDB_API_KEY,
        "query": query,
        "include_adult": False
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(TMDB_SEARCH_URL, params=params) as r:
            if r.status != 200:
                return None, None

            data = await r.json()
            results = data.get("results", [])
            if not results:
                return None, None

            item = results[0]
            poster = item.get("poster_path")
            title = (
                item.get("name")
                or item.get("title")
                or item.get("original_name")
                or item.get("original_title")
            )

            if not poster:
                return None, None

            return title, TMDB_IMAGE_BASE + poster

# ─── BUTTON PARSER ─────────────────────────────────
BTN_REGEX = re.compile(r"\[(.*?)\]\(buttonurl:\/\/(.*?)\)")

def parse_text(text):
    match = BTN_REGEX.search(text)
    if not match:
        return text, None

    button = InlineKeyboardMarkup(
        [[InlineKeyboardButton(match.group(1), url=match.group(2))]]
    )
    clean = BTN_REGEX.sub("", text).strip()
    return clean, button

# ─── START ─────────────────────────────────────────
@app.on_message(filters.command("start") & filters.private)
async def start(_, m: Message):
    await m.reply("🤖 Filter bot running.")

# ─── IMPORT ────────────────────────────────────────
@app.on_message(filters.command("import") & filters.private & filters.user(CONFIG.OWNER_ID))
async def import_filters(_, m: Message):
    import json
    with open("filters.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    await filters_col.delete_many({})

    docs = []
    for item in data:
        docs.append({
            "name": item["name"].lower().strip(),
            "text": item["text"]
        })

    await filters_col.insert_many(docs)
    await m.reply(f"✅ Imported {len(docs)} filters")

# ─── LIST ──────────────────────────────────────────
@app.on_message(filters.command("list") & filters.group)
async def list_filters(_, m: Message):
    if m.chat.id not in CONFIG.ALLOWED_GROUPS:
        return

    names = [x["name"] async for x in filters_col.find({}, {"name": 1})]
    if not names:
        return await m.reply("No filters found")

    text = "\n".join(f"- {n}" for n in names)
    await m.reply(text[:4000])

# ─── MAIN FILTER LOGIC ──────────────────────────────
@app.on_message(filters.group & filters.text & ~filters.command([]))
async def apply_filter(_, m: Message):
    if m.chat.id not in CONFIG.ALLOWED_GROUPS:
        return

    user_text = m.text.lower()
    user_text = re.sub(r"[^\w\s]", "", user_text)
    user_text = re.sub(r"\s+", " ", user_text).strip()

    filters_db = await filters_col.find().to_list(None)

    exact_match = None
    prefix_matches = []

    for f in filters_db:
        fname = f["name"]

        # Exact full match
        if user_text == fname:
            exact_match = f
            break

        # Prefix match
        if fname.startswith(user_text):
            prefix_matches.append(f)

    target = None
    if exact_match:
        target = exact_match
    elif len(prefix_matches) == 1:
        target = prefix_matches[0]
    else:
        return  # 0 ya 2+ match → silent

    # ─── TMDB FETCH ───────────────────────────────
    title, poster = await fetch_tmdb(target["name"])
    if not poster:
        return

    caption_text, buttons = parse_text(target["text"])

    sent = await m.reply_photo(
        poster,
        caption=f"{title}\n\n{caption_text}\n\n_Data & images from TMDB_",
        reply_markup=buttons
    )

    await asyncio.sleep(CONFIG.AUTO_DELETE_TIME)

    try:
        await sent.delete()
        await m.delete()
    except:
        pass

# ─── RUN ───────────────────────────────────────────
print("🤖 Filter Bot Started")
app.run()
