import os

class Config:
    # Telegram API Credentials
    API_ID = 27353035
    API_HASH = "cf2a75861140ceb746c7796e07cbde9e"
    BOT_TOKEN = "8140111290:AAHjF7nJRURv64I1SPWvwKKOAn9R1olrXHo"

    # Bot Owner ID (must be an integer)
    OWNER_ID = 1327021082

    # MongoDB Configuration
    MONGO_URL = "mongodb+srv://satyadipdas24_db_user:HtkJpIxhDM3h1qKh@cluster0.o35rffc.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
    DB_NAME = "filterbot2"

    # Group Management
    # List of allowed group chat IDs (must be integers)
    # Use a negative sign for group IDs, e.g., [-1001234567890]
    ALLOWED_GROUPS = [
        -1001708718174
    ]

    # Auto-Delete Time in seconds (5 minutes = 300 seconds)
    AUTO_DELETE_TIME = 300

    # File path for the filter import JSON (used in /import command)
    IMPORT_FILE_PATH = "/root/Filter/'anime_filter_sections (1).json'"

# Instantiate the configuration
CONFIG = Config()
