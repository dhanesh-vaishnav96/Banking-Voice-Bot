import asyncio
import edge_tts

async def test_edge_tts():
    print("Testing hi-IN-MadhurNeural (Indian Male Hindi)...")
    text = "Namaste Jitesh ji. Main Rahul bol raha hoon ICICI Bank ki taraf se. Aapke account mein paanch hazaar rupaye ki payment baaki hai."
    comm = edge_tts.Communicate(text, "hi-IN-MadhurNeural", rate="+5%")
    await comm.save("test_edge_output.mp3")
    import os
    size = os.path.getsize("test_edge_output.mp3")
    print(f"SUCCESS: Audio generated ({size} bytes) -> test_edge_output.mp3")

asyncio.run(test_edge_tts())
