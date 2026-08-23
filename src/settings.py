from utils import load_config
import configparser
import os
from dotenv import load_dotenv
from logger import logger

load_dotenv()

API_KEY = os.getenv("OPEN_ROUTER_KEY")
TWITCH_API_OAUTH_TOKEN = os.getenv("TWITCH_API_OAUTH_TOKEN")
TWITCH_APP_CLIENT_ID = os.getenv("TWITCH_APP_CLIENT_ID")

config: configparser.ConfigParser = load_config("config")

CLIPCEPTION_ENABLED = config.get("clipception", "enabled").lower() == "true"

# Check for OpenRouter API key
if not API_KEY:
    logger.warning(
        "Warning: OPEN_ROUTER_KEY environment variable is not set. Clipception will be disabled."
    )
    logger.info("You can set it with: export OPEN_ROUTER_KEY='your_key'")
    CLIPCEPTION_ENABLED = False


# Check for Twitch API requirements
if not TWITCH_API_OAUTH_TOKEN or not TWITCH_APP_CLIENT_ID:
    logger.warning(
        "Warning: TWITCH_API_OAUTH_TOKEN and TWITCH_APP_CLIENT_ID "
        "environment variables are not both set. "
        "Set them to increase speed when checking twitch stream statuses."
    )
    logger.info(
        "You can set them with: "
        "export TWITCH_API_OAUTH_TOKEN='your_token' "
        "&& export TWITCH_APP_CLIENT_ID='your_client_id'"
    )
