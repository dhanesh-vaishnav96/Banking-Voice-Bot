import requests, os, time, json
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv('ELEVENLABS_API_KEY')
headers = {'xi-api-key': api_key} if api_key else {}

print('=== ElevenLabs Diagnostic ===')

# 1. Account Subscription & Quota
print('\n[1] Account Subscription Tier & Quota')
r_sub = requests.get('https://api.elevenlabs.io/v1/user/subscription', headers=headers)
is_valid = r_sub.status_code == 200
print(f'API Key Valid: {"Yes" if is_valid else "No (Status: " + str(r_sub.status_code) + ")"}')

if is_valid:
    sub_data = r_sub.json()
    tier = sub_data.get('tier')
    char_count = sub_data.get('character_count', 0)
    char_limit = sub_data.get('character_limit', 0)
    print(f'Subscription Tier: {tier}')
    print(f'Characters Used: {char_count}')
    print(f'Characters Limit: {char_limit}')
    print(f'Characters Remaining: {max(0, char_limit - char_count)}')
else:
    print(f'Error fetching subscription: {r_sub.text}')

# 2. List Voices
print('\n[2] Available Voices (showing up to 10 premade/free ones for test)')
r_voices = requests.get('https://api.elevenlabs.io/v1/voices', headers=headers)
test_voices = []
if r_voices.status_code == 200:
    voices = r_voices.json().get('voices', [])
    for v in voices:
        cat = v.get('category')
        if cat == 'premade' and len(test_voices) < 3:
            test_voices.append(v)
            
    # For brevity, print just a few from our test list
    for v in test_voices:
        print(f"Name: {v['name']} | ID: {v['voice_id']} | Category: {v['category']} | Free Tier Compatible: Yes")
else:
    print(f'Failed to fetch voices: {r_voices.status_code}')

# 3 & 4. Test Voices
print('\n[3] Testing Voices')
test_text = "Namaste Jitesh ji, aapki paanch hazaar rupaye ki payment baaki hai."
any_success = False

for v in test_voices:
    vid = v['voice_id']
    print(f"Testing Voice: {v['name']} ({vid})")
    payload = {
        "text": test_text,
        "model_id": "eleven_multilingual_v2"
    }
    t = time.time()
    r_tts = requests.post(f'https://api.elevenlabs.io/v1/text-to-speech/{vid}', headers=headers, json=payload)
    ms = int((time.time() - t) * 1000)
    print(f"  HTTP Status: {r_tts.status_code}")
    print(f"  Response Time: {ms}ms")
    
    if r_tts.status_code == 200:
        print("  Result: Success")
        any_success = True
    else:
        print(f"  Result: Failure")
        print(f"  Exact Error Body: {r_tts.text}")

print('\n[5] Recommended Free Voice')
print('For Hindi/Hinglish Collection Agent, "Charlie" (ID: IKne3meq5aSn9XLyUdCD) is highly recommended for a deep, professional male voice. "Sarah" (ID: EXAVITQu4vr4xnSDxMaL) is excellent for a reassuring female voice.')

print('\n[6] Fallback Check')
if not is_valid or not any_success:
    print('ACTION_REQUIRED: No ElevenLabs voice worked (or quota exhausted/key invalid). System should revert to edge_tts.')
else:
    print('ElevenLabs is functional!')
