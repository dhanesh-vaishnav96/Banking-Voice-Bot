import asyncio
import httpx

async def test():
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=15) as c:
        r = await c.post("/api/start", json={
            "customer_name": "Mahima Dangi",
            "amount_due": 5000,
            "bank_name": "ICICI Bank",
            "payment_link": "https://pay.icici.com/mahima",
        })
        d = r.json()
        sid = d["session_id"]
        print(f"Session: {sid}")
        print(f"Bot (opening): {d['bot_response']}")
        print()

        turns = [
            ("haan ji bilkul", "Turn 1 - Confirm"),
            ("theek hai", "Turn 2 - Proceed"),
            ("aap kaun bol rahe ho", "Turn 3 - Bank Query"),
            ("link bhej do", "Turn 4 - Payment Link"),
        ]

        for user_text, label in turns:
            r = await c.post("/api/respond", json={"session_id": sid, "user_text": user_text})
            d = r.json()
            print(f"[{label}]")
            print(f"  User: {user_text}")
            print(f"  Intent: {d['intent']}  Stage: {d['stage']}  Provider: {d['llm_provider']}")
            print(f"  Bot: {d['bot_response'][:100]}")
            print()
            if d["is_complete"]:
                print("Conversation complete!")
                break

asyncio.run(test())
