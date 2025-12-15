import os

class Config:
    # Telegram API Credentials
    API_ID = int(os.environ.get("API_ID", 38627319)) # Replace with your API ID
    API_HASH = os.environ.get("API_HASH", "18b0827896e979267ae2251b63830827") # Replace with your API Hash
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "8140111290:AAHjF7nJRURv64I1SPWvwKKOAn9R1olrXHo") # Replace with your Bot Token

    # Bot Owner ID (must be an integer)
    OWNER_ID = int(os.environ.get("OWNER_ID", 1327021082)) # Replace with your Telegram User ID

    # MongoDB Configuration
    MONGO_URL = os.environ.get("MONGO_URL", "mongodb+srv://satyadipdas24_db_user:HtkJpIxhDM3h1qKh@cluster0.o35rffc.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0") # Replace with your MongoDB connection string
    DB_NAME = os.environ.get("DB_NAME", "pyrogram_bot_db")

    # Group Management
    # List of allowed group chat IDs (must be integers)
    # Use a negative sign for group IDs, e.g., [-1001234567890]
    ALLOWED_GROUPS = [int(x) for x in os.environ.get("ALLOWED_GROUPS", "-1002105564295").split(',') if x]
    # Example: ALLOWED_GROUPS = [-1001234567890, -1009876543210]

    # Auto-Delete Time in seconds (5 minutes = 300 seconds)
    AUTO_DELETE_TIME = int(os.environ.get("AUTO_DELETE_TIME", 300))

    # File path for the filter import JSON (used in /import command)
    # This is a placeholder and should be updated by the user or dynamically handled.
    # For now, we'll assume the user will place the file in the home directory.
    IMPORT_FILE_PATH = "/home/ubuntu/upload/anime_filter_sections(1).json"

    # Ensure all critical variables are set for a clean start
    if API_ID == 38627319 or API_HASH == "18b0827896e979267ae2251b63830827" or BOT_TOKEN == "8140111290:AAHjF7nJRURv64I1SPWvwKKOAn9R1olrXHo" or OWNER_ID == 1327021082:
        print("WARNING: Please update API_ID, API_HASH, BOT_TOKEN, and OWNER_ID in config.py or environment variables.")

    if not MONGO_URL.startswith("mongodb"):
        print("mongodb+srv://satyadipdas24_db_user:HtkJpIxhDM3h1qKh@cluster0.o35rffc.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")

    if not ALLOWED_GROUPS:
        print("-1002105564295")

# Instantiate the configuration
CONFIG = Config()
