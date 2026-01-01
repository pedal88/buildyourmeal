
import os
from google import genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

client = genai.Client(api_key=api_key)
print("ALL AVAILABLE MODELS:")
for m in client.models.list():
    print(f"- {m.name}")
