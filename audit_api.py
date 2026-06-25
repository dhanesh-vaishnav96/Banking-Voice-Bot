"""API and performance audit script."""
import requests, time, json, sys

BASE = 'http://127.0.0.1:8000/api'
CUSTOMER = {'customer_name': 'Audit Test', 'amount_due': 5000, 'bank_name': 'HDFC Bank', 'payment_link': 'https://pay.hdfc.com/audit'}

print('=== API ENDPOINT AUDIT ===')
print()

# 1. Health
print('[1] GET /api/health')
t = time.time()
r = requests.get(f'{BASE}/health', timeout=5)
ms = int((time.time()-t)*1000)
print(f'  Status: {r.status_code} | {ms}ms')
print(f'  Body  : {r.json()}')
print()

# 2. Start
print('[2] POST /api/start')
t = time.time()
r = requests.post(f'{BASE}/start', json=CUSTOMER, timeout=10)
ms = int((time.time()-t)*1000)
d = r.json()
sid = d['session_id']
print(f'  Status      : {r.status_code} | {ms}ms')
print(f'  session_id  : {sid}')
print(f'  bot_response: {d["bot_response"]}')
print(f'  stage       : {d["stage"]}')
print(f'  audio_url   : {d["audio_url"]}')
print()

# 3. Respond turns with latency tracking
scenarios = [
    'haan ji main hi bol raha hoon',
    'Mere paas abhi poore paise nahi. Kal 2500 de sakta hoon.',
]
turn_times = []
for i, txt in enumerate(scenarios):
    print(f'[3.{i+1}] POST /api/respond')
    print(f'  user: "{txt}"')
    t = time.time()
    r = requests.post(f'{BASE}/respond', json={'session_id': sid, 'user_text': txt}, timeout=20)
    ms = int((time.time()-t)*1000)
    turn_times.append(ms)
    d = r.json()
    print(f'  Status    : {r.status_code} | {ms}ms')
    print(f'  provider  : {d["llm_provider"]}')
    print(f'  intent    : {d["intent"]}')
    print(f'  stage     : {d["stage"]}')
    print(f'  complete  : {d["is_complete"]}')
    print(f'  bot       : {d["bot_response"]}')
    print()

avg = int(sum(turn_times)/len(turn_times))
print(f'  Turn latency: avg={avg}ms min={min(turn_times)}ms max={max(turn_times)}ms')
print()

# 4. Session state + entity extraction
time.sleep(10)
print(f'[4] GET /api/session/{sid}')
r = requests.get(f'{BASE}/session/{sid}', timeout=5)
d = r.json()
print(f'  Status           : {r.status_code}')
print(f'  stage            : {d["stage"]}')
print(f'  promised_amount  : {d["promised_amount"]}')
print(f'  promised_date    : {d["promised_date"]}')
print(f'  callback_requested:{d["callback_requested"]}')
print(f'  payment_completed: {d["payment_completed"]}')
pc = d.get('post_call_summary')
if pc:
    print(f'  post_call_summary:')
    print(f'    call_summary   : {pc.get("call_summary")}')
    print(f'    customer_intent: {pc.get("customer_intent")}')
    print(f'    payment_commit : {pc.get("payment_commitment")}')
    print(f'    call_outcome   : {pc.get("call_outcome")}')
else:
    print(f'  post_call_summary: None (may still be generating)')
print()

# 5. TTS endpoint
print('[5] POST /api/tts')
r = requests.post(f'{BASE}/tts', json={'text': 'Namaste ji, yeh ek test hai.'}, timeout=10)
print(f'  Status: {r.status_code}')
if r.status_code == 200:
    print(f'  Response: {r.json()}')
else:
    print(f'  Body: {r.text[:300]}')
print()

# 6. 404 handling
print('[6] GET /api/session/INVALID999')
r = requests.get(f'{BASE}/session/INVALID999', timeout=5)
print(f'  Status: {r.status_code} (expected 404)')
print(f'  Detail: {r.json()["detail"]}')
print()

# 7. Input validation
print('[7] POST /api/start - empty name (validation test)')
r = requests.post(f'{BASE}/start', json={'customer_name': '', 'amount_due': 5000, 'bank_name': 'HDFC'}, timeout=5)
print(f'  Status: {r.status_code} (expected 400)')
print(f'  Detail: {r.json()["detail"]}')
print()

# 8. Already completed session guard
print('[8] POST /api/respond on completed session')
r = requests.post(f'{BASE}/respond', json={'session_id': sid, 'user_text': 'hello'}, timeout=5)
print(f'  Status: {r.status_code} (expected 400)')
print(f'  Detail: {r.json()["detail"]}')
print()

# 9. Performance: 5 rapid start calls
print('[9] PERFORMANCE - 5 consecutive /api/start calls')
start_times = []
for i in range(5):
    t = time.time()
    r = requests.post(f'{BASE}/start', json=CUSTOMER, timeout=10)
    ms = int((time.time()-t)*1000)
    start_times.append(ms)
    print(f'  Call {i+1}: {ms}ms (session={r.json()["session_id"]})')
print(f'  Avg start latency: {int(sum(start_times)/len(start_times))}ms')
print()

print('=== API AUDIT COMPLETE ===')
