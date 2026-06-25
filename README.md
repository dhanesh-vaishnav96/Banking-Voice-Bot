# Hindi Voice Collection Bot — POC

A fully working, end-to-end **Hindi Voice Collection Bot** built with:
- **FastAPI** backend (Python)
- **Rule-Based Conversation Engine** (no LLM, pure keyword matching)
- **edge-tts** for natural Hindi TTS (Microsoft Neural voices, free)
- **Browser Web Speech API** for Hindi STT
- **Vanilla HTML/CSS/JS** frontend

---

## Folder Structure

```
voice_collection_bot/
├── backend/
│   ├── main.py                        # FastAPI app entry point
│   ├── config.py                      # Environment config
│   ├── routes/
│   │   └── conversation.py            # API route handlers
│   ├── services/
│   │   ├── conversation_engine.py     # Rule-based conversation logic
│   │   ├── tts.py                     # Text-to-Speech (edge-tts / ElevenLabs)
│   │   └── stt.py                     # Speech-to-Text (Faster-Whisper stub)
│   ├── models/
│   │   └── session.py                 # In-memory session store
│   └── schemas/
│       └── models.py                  # Pydantic API models
├── frontend/
│   ├── index.html                     # Single-page UI
│   ├── css/style.css                  # Enterprise-grade CSS
│   └── js/app.js                      # Frontend logic
├── audio/                             # Generated TTS audio files
├── .env.example                       # Environment config template
├── requirements.txt                   # Python dependencies
└── README.md                          # This file
```

---

## Quick Start

### 1. Prerequisites

- Python 3.10+
- pip

### 2. Setup

```bash
cd voice_collection_bot

# Create virtual environment (recommended)
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment config
copy .env.example .env
```

### 3. Run the Server

```bash
# From the voice_collection_bot directory:
python -m uvicorn backend.main:app --reload --port 8000
```

Or from the parent directory (`Human_AI_Bot`):

```bash
cd voice_collection_bot
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Open the Frontend

Open your browser and go to:

```
http://localhost:8000
```

> **Note:** Use **Google Chrome** for best Web Speech API support.

---

## How to Use

1. **Enter Customer Details** in the left panel (Name, Amount, Bank, Payment Link)
2. Click **▶ Start Conversation** — the bot will speak in Hindi
3. **Click the mic button** 🎤 and speak your response in Hindi
4. The bot will process your response and reply with voice
5. Continue until the conversation completes
6. Click **↺ Reset** to start a new conversation

**Text input** is also available as a fallback — type your response and press Enter or click ➤

---

## Conversation Flow

```
Bot:  "Kya meri baat Jitesh Soni ji se ho rahi hai?"
                  ↓ (User says haan/yes/ji)
Bot:  "Aapka 5000 rupaye ka amount hamare bank mein due hai."
                  ↓ (User responds — any input)
Bot:  "Main ICICI Bank se bol raha hoon. Agar aap abhi payment karna chahte
       hain to main aapko payment link bhej sakta hoon."
                  ↓ (User says haan/bhej do/send karo)
Bot:  "Theek hai. Main aapko payment link bhej raha hoon. [LINK]"
                  ↓
                END
```

**Wrong person flow:**
```
Bot:  "Kya meri baat Jitesh Soni ji se ho rahi hai?"
                  ↓ (User says nahi/no)
Bot:  "Maaf kijiye, mujhe Jitesh Soni ji se hi baat karni thi. Dhanyavaad."
                  ↓
                END
```

---

## How to Demonstrate This POC

For manager presentations or stakeholder reviews, follow these steps to showcase the dynamic, human-like nature of the V2 rule-based engine:

1. **Start the Server:** Ensure the FastAPI server is running (`python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000`).
2. **Load UI:** Open `http://localhost:8000/` in Google Chrome (required for Web Speech API).
3. **Configure details:** Keep default details (Jitesh Soni, ₹5000, ICICI Bank) and click **▶ Start Conversation**.
4. **Trigger cross-cutting intents:** Instead of following a strict script, interrupt the bot at any stage. For example:
   - *Bot: Kya main Jitesh Soni ji se baat kar sakta hoon?*
   - **User:** Aap konse bank se bol rahe ho? *(Demonstrates cross-cutting bank query)*
   - *Bot: Ji main ICICI bank se bol raha hoon...*
   - **User:** Main kal payment karunga. *(Demonstrates cross-cutting delay promise)*
5. **View Summary:** Once the link is sent, click **📋 View Summary** to show the conversation logs, highlighting how the system accurately tracked intents and confidence scores without relying on an LLM.

---

## API Documentation

Interactive API docs are available at: **http://localhost:8000/docs**

### Endpoints

#### `POST /api/start`
Start a new conversation session.

**Request:**
```json
{
  "customer_name": "Jitesh Soni",
  "amount_due": 5000,
  "bank_name": "ICICI Bank",
  "payment_link": "https://pay.example.com/jitesh"
}
```

**Response:**
```json
{
  "session_id": "A3B7F1C2",
  "bot_response": "Kya meri baat Jitesh Soni ji se ho rahi hai?",
  "audio_url": "/audio/response_abc123.mp3",
  "stage": "awaiting_name_confirmation"
}
```

---

#### `POST /api/respond`
Process a user response and get the next bot message.

**Request:**
```json
{
  "session_id": "A3B7F1C2",
  "user_text": "haan"
}
```

**Response:**
```json
{
  "bot_response": "Aapka 5000 rupaye ka amount hamare bank mein due hai.",
  "audio_url": "/audio/response_def456.mp3",
  "stage": "amount_due_information",
  "is_complete": false,
  "payment_link": null
}
```

---

#### `GET /api/session/{session_id}`
Get current session state.

#### `POST /api/transcribe`
(Optional) Server-side Hindi STT using Faster-Whisper.

#### `POST /api/tts`
Convert any text to Hindi audio.

#### `GET /api/voices`
List available TTS voices.

#### `GET /api/health`
Server health check.

---

## Intent Keywords

### Name Confirmation (Affirmative)
`haan`, `han`, `haa`, `ji haan`, `ji han`, `yes`, `ok`, `okay`,
`bol raha hoon`, `main hi`, `bilkul`, `zaroor`, `ji`

### Name Confirmation (Negative / Wrong Person)
`nahi`, `nahin`, `no`, `galat number`, `wrong number`, `main nahi`

### Bank Query
`kaunsa bank`, `kis bank`, `kahan se`, `kaunsi company`,
`aap kaun`, `kahan se call`, `which bank`

### Payment Acceptance
`bhej do`, `send karo`, `send kar do`, `kar do`, `haan`, `han`,
`ok`, `okay`, `yes`, `bilkul`, `zaroor`, `link bhej`

### Payment Decline
`nahi`, `nahin`, `no`, `baad mein`, `abhi nahi`

---

## Sample Test Cases

| Step | User Says | Expected Bot Response |
|------|-----------|----------------------|
| 1    | "Haan"    | "Aapka 5000 rupaye ka amount hamare bank mein due hai." |
| 1    | "Ji haan" | "Aapka 5000 rupaye ka amount..." |
| 1    | "Nahi"    | "Maaf kijiye, mujhe Jitesh Soni ji se hi baat karni thi." |
| 2    | "Kaunsa bank?" | "Main ICICI Bank se bol raha hoon..." |
| 2    | (any response) | "Main ICICI Bank se bol raha hoon..." |
| 3    | "Bhej do" | "Theek hai. Main aapko payment link bhej raha hoon..." |
| 3    | "Nahi chahiye" | "Koi baat nahi. Jab bhi aap payment karna chahein..." |

---

## TTS Configuration

### Default: edge-tts (Free, No API Key)

Available Hindi voices:
- `hi-IN-SwaraNeural` — Female (default)
- `hi-IN-MadhurNeural` — Male

To change voice, update `.env`:
```
EDGE_TTS_DEFAULT_VOICE=hi-IN-MadhurNeural
```

### Optional: ElevenLabs

1. Get an API key from [ElevenLabs](https://elevenlabs.io)
2. Update `.env`:
```
TTS_PROVIDER=elevenlabs
ELEVENLABS_API_KEY=your_key_here
ELEVENLABS_VOICE_ID=your_voice_id
```

---

## STT Configuration

### Default: Browser Web Speech API

- Works in Google Chrome
- No setup required
- Language: `hi-IN` (Hindi)

### Optional: Faster-Whisper (Server-Side)

1. Uncomment in `requirements.txt`: `faster-whisper>=1.0.1`
2. Install: `pip install faster-whisper`
3. Update `.env`: `STT_PROVIDER=faster_whisper`
4. First run will download the Whisper model (~150MB for `small`)

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Mic not working | Use Google Chrome; allow mic permissions |
| Hindi not recognized | Ensure Chrome is set to recognize `hi-IN` |
| No audio playback | Check browser autoplay policy; click once on page first |
| `edge-tts` error | Run `pip install edge-tts --upgrade` |
| Server not starting | Ensure you're in `voice_collection_bot/` directory |
| CORS error | Make sure frontend is served from the same FastAPI server |

---

## Success Criteria Verification

- ✅ Bot sounds human-like (Microsoft Neural Hindi voices)
- ✅ Customer name, amount, bank dynamically injected
- ✅ User can speak via microphone (Web Speech API)
- ✅ Bot understands Hindi keyword variations
- ✅ Bot replies correctly per conversation state
- ✅ Hindi pronunciation is natural (Neural TTS)
- ✅ End-to-end conversation works without manual intervention
