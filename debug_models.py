import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
print(f"Key present: {bool(api_key)}")

client = genai.Client(api_key=api_key)

try:
    print("Listing models...")
    # Try to list models to see what's available
    # Iterate directly if iterable, or check methods
    pager = client.models.list()
    for m in pager:
        # Display name and id
        print(f"Model: {m.name} | Display Name: {m.display_name}")
except Exception as e:
    print(f"List Error: {e}")
