import asyncio
import httpx
import json
import time
from rich.console import Console

console = Console()
BASE_URL = "http://localhost:8000"

async def run_scenario(scenario_name: str, turns: list):
    console.print(f"\n[bold cyan]==================================================[/bold cyan]")
    console.print(f"[bold cyan]SCENARIO: {scenario_name}[/bold cyan]")
    console.print(f"[bold cyan]==================================================[/bold cyan]")

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=40) as client:
        # Start Call
        start_res = await client.post("/api/start", json={
            "customer_name": "Jitesh Soni",
            "amount_due": 5000,
            "bank_name": "HDFC Bank",
            "payment_link": "https://pay.hdfc.com/jitesh-5000"
        })
        d = start_res.json()
        sid = d["session_id"]
        console.print(f"[bold green]Bot (Stage: {d['stage']}):[/bold green] {d['bot_response']}")
        
        await asyncio.sleep(5) # Delay to respect rate limits

        # Process Turns
        for turn in turns:
            console.print(f"\n[bold yellow]User:[/bold yellow] {turn}")
            t_start = time.time()
            res = await client.post("/api/respond", json={"session_id": sid, "user_text": turn})
            d = res.json()
            elapsed = int((time.time() - t_start) * 1000)
            
            console.print(f"[bold green]Gemini Response:[/bold green] {d['bot_response']}")
            console.print(f"  [dim]Intent: {d['intent']} | Stage: {d['stage']} | LLM Provider: {d['llm_provider']} ({elapsed}ms)[/dim]")
            
            if d.get("is_complete"):
                break
                
            await asyncio.sleep(5) # Delay between turns
                
        # Wait for async summary generation (allow 20 seconds for Gemini API)
        console.print("\n[dim]Waiting 20 seconds for Gemini Post-Call Summary generation...[/dim]")
        await asyncio.sleep(20)

        # Get final session state and summary
        state_res = await client.get(f"/api/session/{sid}/summary")
        if state_res.status_code == 200:
            state = state_res.json()
            console.print(f"\n[bold magenta]Phase 2 Tracked Entities:[/bold magenta]")
            console.print(f"  - Promised Date: {state.get('promised_date')}")
            console.print(f"  - Promised Amount: {state.get('promised_amount')}")
            console.print(f"  - Callback Requested: {state.get('callback_requested')}")
            console.print(f"  - Payment Completed: {state.get('payment_completed')}")
            
            summary = state.get("post_call_summary")
            if summary:
                console.print(f"\n[bold magenta]Post-Call Summary (Gemini JSON):[/bold magenta]")
                console.print(json.dumps(summary, indent=2))
            else:
                console.print("\n[bold red]Error: No post-call summary generated![/bold red]")


async def main():
    scenarios = [
        ("Partial Payment", [
            "haan ji", 
            "Mere paas abhi poore paise nahi hain. Main kal 2500 rupaye de sakta hoon."
        ]),
        ("Supervisor Request", [
            "haan bol raha hoon", 
            "Main aapke manager se baat karna chahta hoon."
        ]),
        ("Already Paid", [
            "ji haan", 
            "Maine payment kal kar diya tha."
        ])
    ]

    for name, turns in scenarios:
        await run_scenario(name, turns)
        console.print("\n[dim]Waiting 15 seconds before next scenario to avoid API quotas...[/dim]")
        await asyncio.sleep(15)

if __name__ == "__main__":
    asyncio.run(main())
