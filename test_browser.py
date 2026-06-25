import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--use-fake-ui-for-media-stream'])
        page = await browser.new_page()
        
        page.on("console", lambda msg: print(f"BROWSER LOG: {msg.text}"))
        
        print("Navigating...")
        await page.goto("http://localhost:8000")
        
        print("Filling out form...")
        await page.fill('#customer-name', 'Mahima Dangi')
        await page.fill('#amount-due', '5000')
        await page.fill('#bank-name', 'ICICI Bank')
        
        print("Clicking Start...")
        await page.click('#start-btn')
        
        print("Waiting 6 seconds for first bot audio to finish...")
        await asyncio.sleep(6)
        
        print("Simulating STT by typing 'haan'...")
        await page.fill('#text-input', 'haan')
        await page.click('#send-btn')
        
        print("Waiting 6 seconds for second bot audio to finish...")
        await asyncio.sleep(6)
        
        print("Simulating STT by typing 'theek hai'...")
        await page.fill('#text-input', 'theek hai')
        await page.click('#send-btn')
        
        print("Waiting 6 seconds for third bot audio to finish...")
        await asyncio.sleep(6)
        
        await browser.close()

if __name__ == '__main__':
    asyncio.run(main())
