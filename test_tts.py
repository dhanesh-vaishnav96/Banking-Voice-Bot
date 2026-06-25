import asyncio
import edge_tts

async def main():
    text = "Ji, main ICICI Bank se bol raha hoon. Aapke account mein 5000 rupaye pending hain. Kya main aapko abhi payment link bhej dun? Aap ek click mein payment kar sakte hain."
    
    # Madhur, fast
    comm_m = edge_tts.Communicate(text, "hi-IN-MadhurNeural", rate="+20%")
    await comm_m.save("madhur_fast.mp3")
    
    # Swara, fast
    comm_s = edge_tts.Communicate(text, "hi-IN-SwaraNeural", rate="+20%")
    await comm_s.save("swara_fast.mp3")

asyncio.run(main())
