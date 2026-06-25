import httpx
import asyncio

API_KEY = "sk_4eec7ea43da2e4e170f1847c74d4383c42bff7c8360ceaea"
VOICE_ID = "IKne3meq5aSn9XLyUdCD"

async def test():
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
    headers = {
        "xi-api-key": API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": "Namaste Jitesh ji. Main ICICI Bank se bol raha hoon.",
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.50,
            "similarity_boost": 0.75,
            "style": 0.20,
            "use_speaker_boost": True,
        },
    }

    print(f"Testing ElevenLabs API...")
    print(f"Voice ID: {VOICE_ID}")
    print(f"API Key (first 12 chars): {API_KEY[:12]}...")

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, json=payload, headers=headers)
        print(f"\nHTTP Status: {response.status_code}")
        print(f"Content-Type: {response.headers.get('content-type', 'unknown')}")
        print(f"Response size: {len(response.content)} bytes")
        if response.status_code == 200:
            with open("test_audio.mp3", "wb") as f:
                f.write(response.content)
            print("SUCCESS: Audio saved to test_audio.mp3")
        else:
            print(f"ERROR body: {response.text[:500]}")

asyncio.run(test())
