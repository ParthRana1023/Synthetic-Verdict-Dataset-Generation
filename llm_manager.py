import os
from itertools import cycle
from dotenv import load_dotenv

load_dotenv()

# Load keys as a list
api_keys = os.getenv("GROQ_API_KEYS", "").split(",")
api_keys = [k.strip() for k in api_keys if k.strip()]

if not api_keys:
    raise ValueError("❌ No GROQ_API_KEYS found in .env file")

# Cycle through keys
key_cycle = cycle(api_keys)
current_key = next(key_cycle)

def get_current_key():
    global current_key
    return current_key

def rotate_key():
    global current_key
    current_key = next(key_cycle)
    print(f"🔑 Switched to next API key: {current_key[:6]}...")  # log safely
    return current_key
