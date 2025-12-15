import asyncio
import json
import re
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram.enums import ChatType
from motor.motor_asyncio import AsyncIOMotorClient
from config import CONFIG

# -------------------- MongoDB --------------------
mongo_client = AsyncIOMotorClient(CONFIG.MONGO_URL)
db = mongo_client[CONFIG.DB_NAME]
filters_collection = db.filters

# -------------------- Button Parser --------------------
BUTTON_REGEX = re.compile(r"\[(.*?)\]\(buttonurl:\/\/(.*?)\)")

def parse_filter_text(text: str):
    match = BUTTON_REGEX.search(text)
    if not match:
        return text, None

    btn_text = match.group(1)
    btn_url = match.group(2)
    clean_text = BUTTON_REGEX.sub("", text).strip()

    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton(btn_text, url=btn_url)]]
    )
    return clean_text, keyboard

# -------------------- Custom Filters --------------------
def owner_only(_, __, msg: Message):
    return msg.from_user and msg.from_user.id == CONFIG.OWNER_ID

def private_only(_, __, msg: Message):
    return msg.chat.type == ChatType.PRIVATE

def group_only(_, __, msg: Message):
    return msg.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP)

def allowed_group(_, __, msg: Message):
    return msg.chat.id in CONFIG.ALLOWED_GROUPS

def not_edited(_, __, msg: Message):
    return msg.edit_date is None

owner_filter = filters.create(owner_only)
private_filter = filters.create(private_only)
group_filter = filters.create(group_only)
allowed_group_filter = filters.create(allowed_group)
not_edited_filter = filters.create(not_edited)

# -------------------- Bot Init --------------------
app = Client(
    "filter-bot",
    api_id=CONFIG.API_ID,
    api_hash=CONFIG.API_HASH,
    bot_token=CONFIG.BOT_TOKEN
)

# -------------------- Commands --------------------
@app.on_message(filters.command("start") & private_filter)
async def start(_, msg: Message):
    await msg.reply_text(
        "Hello 👋\n\n"
        "• /import → Import filters (Owner only)\n"
        "• /list → List filters (Group)\n"
        "• /del <name> → Delete filter (Owner)"
    )

@app.on_message(filters.command("import") & private_filter & owner_filter)
async def import_filters(_, msg: Message):
    try:
        with open(CONFIG.IMPORT_FILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        await filters_collection.delete_many({})

        docs = []
        for item in data:
            if "name" in item and "text" in item:
                name = item["name"].lower().strip()
                keywords = name.split()  # 👈 IMPORTANT

                docs.append({
                    "name": name,
                    "text": item["text"],
                    "keywords": keywords
                })

        if docs:
            await filters_collection.insert_many(docs)
            await msg.reply_text(f"✅ Imported {len(docs)} filters")
        else:
            await msg.reply_text("⚠️ No valid filters found")

    except Exception as e:
        await msg.reply_text(f"❌ Import failed:\n`{e}`")

@app.on_message(filters.command("list") & group_filter & allowed_group_filter)
async def list_filters(_, msg: Message):
    cursor = filters_collection.find({}, {"name": 1}).sort("name", 1)
    names = [doc["name"] async for doc in cursor]

    if not names:
        await msg.reply_text("No filters found.")
        return

    text = "**Available Filters:**\n\n"
    text += "\n".join(f"• `{n}`" for n in names[:100])

    await msg.reply_text(text)

@app.on_message(filters.command("del") & group_filter & allowed_group_filter & owner_filter)
async def delete_filter(_, msg: Message):
    if len(msg.command) < 2:
        await msg.reply_text("Usage: /del <filter_name>")
        return

    name = " ".join(msg.command[1:]).lower().strip()
    res = await filters_collection.delete_one({"name": name})

    if res.deleted_count:
        await msg.reply_text(f"✅ Deleted `{name}`")
    else:
        await msg.reply_text("❌ Filter not found")

# -------------------- FILTER MATCHING (FIXED) --------------------
@app.on_message(
    group_filter &
    allowed_group_filter &
    filters.text &
    ~filters.command([]) &
    not_edited_filter
)
async def apply_filter(_, msg: Message):
    text = msg.text.lower()

    words = re.findall(r"\w+", text)  # split safely

    filter_doc = await filters_collection.find_one({
        "keywords": {"$in": words}
    })

    if not filter_doc:
        return

    reply_text, keyboard = parse_filter_text(filter_doc["text"])

    reply = await msg.reply_text(
        reply_text,
        reply_markup=keyboard,
        disable_web_page_preview=True
    )

    # Auto delete after time
    await asyncio.sleep(CONFIG.AUTO_DELETE_TIME)

    try:
        await reply.delete()
    except:
        pass

    try:
        await msg.delete()
    except:
        pass

# -------------------- Run --------------------
if __name__ == "__main__":
    print("🤖 Filter Bot Running")
    app.run()
