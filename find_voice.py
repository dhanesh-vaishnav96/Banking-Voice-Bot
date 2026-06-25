import os
import httpx
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("ELEVENLABS_API_KEY")

def list_voices():
    url = "https://api.elevenlabs.io/v1/voices"
    headers = {"xi-api-key": api_key}
    print("Querying ElevenLabs API...")
    response = httpx.get(url, headers=headers)
    
    if response.status_code != 200:
        print(f"Error fetching voices: {response.status_code} {response.text}")
        return
        
    voices = response.json().get("voices", [])
    
    print(f"Found {len(voices)} voices. Filtering for 'premade' (free tier compatible)...")
    
    free_tier_voices = []
    for voice in voices:
        voice_id = voice.get("voice_id")
        name = voice.get("name")
        category = voice.get("category")
        labels = voice.get("labels", {})
        
        if category == "premade":
            free_tier_voices.append((voice_id, name, labels))
            
    print("\n--- Free Tier (Premade) Voices ---")
    for vid, name, labels in free_tier_voices:
        print(f"ID: {vid} | Name: {name} | Labels: {labels}")

if __name__ == "__main__":
    list_voices()
