import asyncio
from playwright.async_api import async_playwright

mock_script = """
class MockSpeechRecognition {
    constructor() {
        this.continuous = false;
        this.interimResults = false;
        this.lang = 'en-US';
        this.isListening = false;
        window.__mockMic = this;
    }
    start() {
        if (this.isListening) {
            if (this.onerror) this.onerror({error: 'not-allowed'});
            return;
        }
        this.isListening = true;
        console.log('[MOCK] SpeechRecognition.start() called');
        if (this.onstart) setTimeout(() => this.onstart(), 10);
    }
    stop() {
        if (!this.isListening) return;
        this.isListening = false;
        console.log('[MOCK] SpeechRecognition.stop() called');
        if (this.onend) setTimeout(() => this.onend(), 10);
    }
    abort() {
        if (!this.isListening) return;
        this.isListening = false;
        console.log('[MOCK] SpeechRecognition.abort() called');
        if (this.onend) setTimeout(() => this.onend(), 10);
    }
    
    // Test helper to simulate user speaking
    simulateSpeech(text) {
        if (!this.isListening) return;
        console.log('[MOCK] Simulating speech: ' + text);
        this.isListening = false; // continuous=false behavior
        if (this.onresult) {
            this.onresult({
                results: [[ { transcript: text } ]]
            });
        }
        if (this.onend) setTimeout(() => this.onend(), 10);
    }
    
    // Test helper to simulate silence
    simulateSilence() {
        if (!this.isListening) return;
        console.log('[MOCK] Simulating silence (no-speech)');
        this.isListening = false;
        if (this.onerror) this.onerror({error: 'no-speech'});
        if (this.onend) setTimeout(() => this.onend(), 10);
    }
}
window.SpeechRecognition = MockSpeechRecognition;
window.webkitSpeechRecognition = MockSpeechRecognition;
"""

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Inject the mock before any script runs
        await page.add_init_script(mock_script)
        
        logs = []
        page.on("console", lambda msg: logs.append(f"BROWSER LOG: {msg.text}"))
        
        print("Navigating...")
        await page.goto("http://localhost:8000")
        
        await page.fill('#customer-name', 'Mahima Dangi')
        await page.fill('#amount-due', '5000')
        await page.fill('#bank-name', 'ICICI Bank')
        
        print("Clicking Start...")
        await page.click('#start-btn')
        
        print("Turn 1: Waiting for bot audio 1 to finish...")
        await asyncio.sleep(6) # Namaste! Kya main Mahima Dangi ji se baat...
        
        print("Simulating User: haan")
        await page.evaluate("window.__mockMic.simulateSpeech('haan')")
        
        print("Turn 2: Waiting for bot audio 2 to finish...")
        await asyncio.sleep(11) # Amount information is a bit long
        
        print("Simulating User: theek hai (Silence test next)")
        await page.evaluate("window.__mockMic.simulateSpeech('theek hai')")
        
        print("Turn 3: Waiting for bot audio 3 to finish...")
        await asyncio.sleep(8) # Bank information
        
        print("Testing Silence Timeout... waiting 6 seconds")
        await asyncio.sleep(6) # Audio ended, mic started, waiting for user
        await page.evaluate("window.__mockMic.simulateSilence()") # trigger no-speech
        
        print("Silence triggered. Waiting 2 seconds for auto-restart...")
        await asyncio.sleep(2)
        
        print("Simulating User: bhej do (Payment accept)")
        await page.evaluate("window.__mockMic.simulateSpeech('bhej do')")
        
        print("Turn 4: Waiting for bot audio 4 to finish (Conversation Completed)")
        await asyncio.sleep(6)
        
        print("Done.")
        await browser.close()
        
        with open("browser_test_logs.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(logs))
        print("Logs saved to browser_test_logs.txt")

if __name__ == '__main__':
    asyncio.run(main())
