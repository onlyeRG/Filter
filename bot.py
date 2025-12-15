import asyncio
import json
import re
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram.enums import ChatType
from motor.motor_asyncio import AsyncIOMotorClient
from config import CONFIG

# --- MongoDB Setup ---
mongo_client = AsyncIOMotorClient(CONFIG.MONGO_URL)
db = mongo_client[CONFIG.DB_NAME]
filters_collection = db.filters

# --- Utility Functions ---

BUTTON_REGEX = re.compile(r"\[(.*?)\]$$buttonurl:\/\/(.*?)$$")

def parse_filter_text(text: str) -> tuple[str, InlineKeyboardMarkup | None]:
    """
    Parses the filter text to separate the message content from the inline button.
    Returns the clean text and an optional InlineKeyboardMarkup.
    """
    match = BUTTON_REGEX.search(text)
    if not match:
        return text, None

    button_text = match.group(1)
    button_url = match.group(2)
    clean_text = BUTTON_REGEX.sub("", text).strip()

    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton(button_text, url=button_url)]]
    )
    return clean_text, keyboard

# --- Custom Filters ---

def owner_only(_, __, msg: Message):
    """Filter for messages sent by the bot owner."""
    return msg.from_user and msg.from_user.id == CONFIG.OWNER_ID

def private_chat_only(_, __, msg: Message):
    """Filter for messages in a private chat."""
    return msg.chat.type == ChatType.PRIVATE

def group_chat_only(_, __, msg: Message):
    """Filter for messages in a group or supergroup."""
    return msg.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP)

def allowed_group_only(_, __, msg: Message):
    """Filter for messages in an allowed group."""
    return msg.chat.id in CONFIG.ALLOWED_GROUPS

def not_edited(_, __, msg: Message):
    """Filter to ignore edited messages."""
    return msg.edit_date is None

# Combine custom filters
owner_filter = filters.create(owner_only)
private_filter = filters.create(private_chat_only)
group_filter = filters.create(group_chat_only)
allowed_group_filter = filters.create(allowed_group_only)
not_edited_filter = filters.create(not_edited)

# --- Pyrogram Client Initialization ---
app = Client(
    "pyrogram_bot",
    api_id=CONFIG.API_ID,
    api_hash=CONFIG.API_HASH,
    bot_token=CONFIG.BOT_TOKEN
)

# --- Handlers ---

@app.on_message(filters.command("start") & private_filter)
async def start_handler(_, msg: Message):
    """Basic start command handler for private chat."""
    await msg.reply_text(
        "Hello! I am your filter bot. Use /import to add filters (Owner only)."
    )

@app.on_message(filters.command("import") & private_filter & owner_filter)
async def import_handler(_, msg: Message):
    """
    Handler for the /import command.
    Works only in private chat and only for the bot owner.
    Imports filters from the specified JSON file into MongoDB.
    """
    try:
        with open(CONFIG.IMPORT_FILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Clear existing filters and insert new ones
        await filters_collection.delete_many({})
        
        # Prepare data for insertion, ensuring required fields are present
        filters_to_insert = []
        for item in data:
            if "name" in item and "text" in item:
                filters_to_insert.append({
                    "name": item["name"].lower(), # Store name in lowercase for case-insensitive matching
                    "text": item["text"],
                    "keywords": [item["name"].lower()] # Use the name as the primary keyword for now
                })

        if filters_to_insert:
            await filters_collection.insert_many(filters_to_insert)
            await msg.reply_text(
                f"Successfully imported **{len(filters_to_insert)}** filters from `{CONFIG.IMPORT_FILE_PATH}`."
            )
        else:
            await msg.reply_text("The import file is empty or contains no valid filters.")

    except FileNotFoundError:
        await msg.reply_text(
            f"Error: Import file not found at `{CONFIG.IMPORT_FILE_PATH}`. "
            "Please ensure the file is present and the path in `config.py` is correct."
        )
    except json.JSONDecodeError:
        await msg.reply_text("Error: Failed to decode JSON from the import file. Please check the file format.")
    except Exception as e:
        await msg.reply_text(f"An unexpected error occurred during import: `{e}`")

@app.on_message(filters.command("list") & group_filter & allowed_group_filter)
async def list_handler(_, msg: Message):
    """
    Handler for the /list command.
    Works only in allowed groups. Lists all filter names.
    """
    try:
        # Fetch all filter names, sorted alphabetically
        cursor = filters_collection.find({}, {"name": 1}).sort("name", 1)
        filters_list = [f["name"] for f in await cursor.to_list(length=None)]

        if not filters_list:
            await msg.reply_text("No filters have been added yet.")
            return

        # Format the list into a readable message
        header = f"**Total Filters: {len(filters_list)}**\n\n"
        body = "\n".join(f"- `{name}`" for name in filters_list)
        
        # Telegram message limit is 4096 characters
        if len(header + body) > 4096:
            # Simple truncation for now, a better solution would be to send multiple messages
            body = body[:4000] + "\n..."

        await msg.reply_text(header + body)

    except Exception as e:
        await msg.reply_text(f"An error occurred while listing filters: `{e}`")

@app.on_message(filters.command("del") & group_filter & allowed_group_filter & owner_filter)
async def delete_handler(_, msg: Message):
    """
    Handler for the /del <filter_name> command.
    Works only in allowed groups and only for the bot owner.
    Deletes a filter by name.
    """
    if len(msg.command) < 2:
        await msg.reply_text("Usage: `/del <filter_name>`")
        return

    filter_name = " ".join(msg.command[1:]).lower()

    try:
        result = await filters_collection.delete_one({"name": filter_name})

        if result.deleted_count == 1:
            await msg.reply_text(f"Filter `{filter_name}` successfully deleted.")
        else:
            await msg.reply_text(f"Filter `{filter_name}` not found.")

    except Exception as e:
        await msg.reply_text(f"An error occurred while deleting the filter: `{e}`")

@app.on_message(group_filter & allowed_group_filter & ~filters.command([]) & not_edited_filter)
async def filter_message_handler(_, msg: Message):
    """
    Handler for non-command text messages in allowed groups.
    Applies filters based on message text.
    """
    if not msg.text:
        return

    # Convert the message text to lowercase for case-insensitive matching
    search_text = msg.text.lower()
    
    # Find all filters and check if any filter name appears as a substring in the message
    cursor = filters_collection.find({})
    all_filters = await cursor.to_list(length=None)
    
    # Look for the first filter whose name is contained in the message text
    filter_doc = None
    for f in all_filters:
        if f["name"] in search_text:
            filter_doc = f
            break

    if filter_doc:
        # Filter found, process the reply
        raw_text = filter_doc["text"]
        clean_text, reply_markup = parse_filter_text(raw_text)

        # Send the reply
        reply_msg = await msg.reply_text(
            clean_text,
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )

        # Schedule auto-deletion
        await asyncio.sleep(CONFIG.AUTO_DELETE_TIME)
        
        # Attempt to delete both messages
        try:
            await reply_msg.delete()
        except Exception:
            # Ignore errors if the message is already deleted or bot lacks permission
            pass
        
        try:
            await msg.delete()
        except Exception:
            # Ignore errors if the message is already deleted or bot lacks permission
            pass

# --- Main Execution ---

if __name__ == "__main__":
    print("Starting bot...")
    app.run()
    print("Bot stopped.")
