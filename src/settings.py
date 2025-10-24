from utils import load_config
import configparser
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("OPEN_ROUTER_KEY")
config: configparser.ConfigParser = load_config("config")

CLIPCEPTION_ENABLED = config.get("clipception", "enabled").lower() == "true"

# Check for OpenRouter API key
if not API_KEY:
    print(
        "Warning: OPEN_ROUTER_KEY environment variable is not set. Clipception will be disabled."
    )
    print("You can set it with: export OPEN_ROUTER_KEY='your_key'")
    CLIPCEPTION_ENABLED = False
