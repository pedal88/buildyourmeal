import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai.types import GenerateContentConfig

load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")
project_id = os.getenv("GOOGLE_CLOUD_PROJECT")

print(f"--- Configuration Check ---")
print(f"Project ID from .env: {project_id}")
print(f"API Key present: {bool(api_key)}")
if api_key:
    print(f"API Key prefix: {api_key[:8]}...")

if not api_key:
    print("ERROR: No API Key found.")
    exit(1)

client = genai.Client(api_key=api_key)

print("\n--- Model Availability Check ---")
try:
    # List models to confirm what we can see
    pager = client.models.list()
    found_models = [m.name for m in pager]
    print(f"Found {len(found_models)} models.")
    
    # Check for specific models
    for target in ['gemini-1.5-flash', 'gemini-2.0-flash']:
        # The list returns full resource names like 'models/gemini-1.5-flash'
        match = any(target in m for m in found_models)
        print(f"Model '{target}' available: {match}")

except Exception as e:
    print(f"Error listing models: {e}")

print("\n--- Billing/Quota Check (attempting generation) ---")
# Try a simple generation with 1.5 Flash (Standard Paid Model)
try:
    print("Attempting generation with 'gemini-1.5-flash'...")
    response = client.models.generate_content(
        model='gemini-1.5-flash',
        contents='Hello, are you working?'
    )
    print("Success! (Billing likely working or within free tier)")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error with gemini-1.5-flash: {e}")

print("\n--- 2.0 Check ---")
try:
    print("Attempting generation with 'gemini-2.0-flash'...")
    response = client.models.generate_content(
        model='gemini-2.0-flash',
        contents='Hello, are you working?'
    )
    print("Success! (gemini-2.0-flash working)")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error with gemini-2.0-flash: {e}")
