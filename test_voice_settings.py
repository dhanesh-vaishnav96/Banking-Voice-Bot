import requests, os, time, json
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv('ELEVENLABS_API_KEY')
voice_id = 'IKne3meq5aSn9XLyUdCD' # Charlie
url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
headers = {"xi-api-key": api_key, "Content-Type": "application/json"}

sample_text = "Namaste Jitesh ji, main Rahul bol raha hoon HDFC Bank ki taraf se. Aapke account mein paanch hazaar rupaye ki payment baaki hai."

configs = [
    {"name": "1. Baseline", "s": 0.45, "sim": 0.80, "style": 0.35, "boost": True},
    {"name": "2. High Stability (News Anchor)", "s": 0.80, "sim": 0.80, "style": 0.0, "boost": True},
    {"name": "3. High Expressiveness (Emotional)", "s": 0.30, "sim": 0.70, "style": 0.60, "boost": True},
    {"name": "4. Natural Conversational (Balanced)", "s": 0.50, "sim": 0.75, "style": 0.20, "boost": True},
    {"name": "5. Hyper-Realistic (Slightly shaky)", "s": 0.35, "sim": 0.85, "style": 0.10, "boost": False},
]

print("=== Voice Quality Optimization Test ===")
print("Testing 5 configurations for Charlie...\n")

for c in configs:
    payload = {
        "text": sample_text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": c["s"],
            "similarity_boost": c["sim"],
            "style": c["style"],
            "use_speaker_boost": c["boost"]
        }
    }
    t = time.time()
    r = requests.post(url, headers=headers, json=payload)
    ms = int((time.time()-t)*1000)
    print(f"Config: {c['name']}")
    print(f"  Stability: {c['s']} | Similarity: {c['sim']} | Style: {c['style']} | Boost: {c['boost']}")
    print(f"  Latency: {ms}ms | Status: {r.status_code}")
    print()

print("=== Pronunciation Check ===")
pronounce_text = "paanch hazaar, HDFC, ICICI, payment link, kal payment kar dijiye."
payload["text"] = pronounce_text
t = time.time()
r = requests.post(url, headers=headers, json=payload)
print(f"Pronunciation text test status: {r.status_code} ({int((time.time()-t)*1000)}ms)")
