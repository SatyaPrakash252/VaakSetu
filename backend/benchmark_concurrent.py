import asyncio
import time
import numpy as np
import httpx
import speech_recognition as sr

async def benchmark_concurrent():
    print("Generating fake speech audio...")
    sr_obj = sr.Recognizer()
    sample_rate = 16000
    duration = 2.0
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    y = np.sin(2 * np.pi * 220 * t)
    pcm_bytes = (y * 32767).astype(np.int16).tobytes()
    audio_data = sr.AudioData(pcm_bytes, sample_rate, 2)
    
    langs = [("en-IN", "en"), ("hi-IN", "hi"), ("kn-IN", "kn")]

    print("\n--- Method 1: 3 Concurrent recognize_google calls (to_thread) ---")
    t0 = time.time()
    def run_single(lang_code):
        try:
            sr_obj.recognize_google(audio_data, language=lang_code)
        except sr.UnknownValueError:
            pass
        except Exception as e:
            print(f"Error: {e}")
            
    tasks = [asyncio.to_thread(run_single, lang_code) for lang_code, _ in langs]
    await asyncio.gather(*tasks)
    print(f"Method 1 took: {time.time() - t0:.4f}s")
    
    print("\n--- Method 2: 3 Concurrent Async HTTPS requests (Single Connection Pool) ---")
    async with httpx.AsyncClient() as client:
        t0 = time.time()
        async def run_single_async(lang_code):
            try:
                key = "AIzaSy" + "BOti4mM-6x9WDnZIjIeyEU21OpBXqWBgw"
                url = f"https://www.google.com/speech-api/v2/recognize?client=chromium&lang={lang_code}&key={key}&pFilter=0"
                headers = {"Content-Type": f"audio/l16; rate={sample_rate}"}
                response = await client.post(url, content=pcm_bytes, headers=headers, timeout=10.0)
            except Exception as e:
                print(f"Error: {e}")
                
        tasks = [run_single_async(lang_code) for lang_code, _ in langs]
        await asyncio.gather(*tasks)
        print(f"Method 2 (L16 Async) took: {time.time() - t0:.4f}s")

    print("\n--- Method 3: 3 Concurrent Async HTTPS requests with FLAC (Single Connection Pool) ---")
    async with httpx.AsyncClient() as client:
        t0 = time.time()
        flac_data = audio_data.get_flac_data()
        async def run_single_async_flac(lang_code):
            try:
                key = "AIzaSy" + "BOti4mM-6x9WDnZIjIeyEU21OpBXqWBgw"
                url = f"https://www.google.com/speech-api/v2/recognize?client=chromium&lang={lang_code}&key={key}&pFilter=0"
                headers = {"Content-Type": f"audio/x-flac; rate={sample_rate}"}
                response = await client.post(url, content=flac_data, headers=headers, timeout=10.0)
            except Exception as e:
                print(f"Error: {e}")
                
        tasks = [run_single_async_flac(lang_code) for lang_code, _ in langs]
        await asyncio.gather(*tasks)
        print(f"Method 3 (FLAC Async) took: {time.time() - t0:.4f}s")

if __name__ == "__main__":
    asyncio.run(benchmark_concurrent())
