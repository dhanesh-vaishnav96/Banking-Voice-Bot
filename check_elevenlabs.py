import httpx
import asyncio

API_KEY = "sk_4eec7ea43da2e4e170f1847c74d4383c42bff7c8360ceaea"

async def check_account():
    print("=== ElevenLabs Account Status ===")
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(
            "https://api.elevenlabs.io/v1/user",
            headers={"xi-api-key": API_KEY}
        )
        print(f"HTTP Status: {r.status_code}")
        data = r.json()
        sub = data.get("subscription", {})
        used = sub.get("character_count", 0)
        limit = sub.get("character_limit", 0)
        remaining = limit - used
        print(f"Tier: {sub.get('tier', 'unknown')}")
        print(f"Characters used: {used}")
        print(f"Characters limit: {limit}")
        print(f"Characters REMAINING: {remaining}")
        if remaining <= 0:
            print("\n❌ CONFIRMED: Account has ZERO credits. ElevenLabs will NOT work.")
            print("Action: Please provide a new API key from another ElevenLabs account.")
        else:
            print(f"\n✅ Account has {remaining} credits available.")

asyncio.run(check_account())
