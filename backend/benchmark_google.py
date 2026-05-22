import asyncio
import time
import base64
import numpy as np
import httpx
import speech_recognition as sr

async def benchmark():
    print("Generating fake speech audio (sine waves / silence)...")
    # Let's read a real WAV file or generate a valid WAV format from audio data
    sr_obj = sr.Recognizer()
    
    # Let's generate a 2-second 220Hz sine wave as WAV
    sample_rate = 16000
    duration = 2.0
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    y = np.sin(2 * np.pi * 220 * t)
    # Convert numpy float32 to int16 PCM bytes
    pcm_bytes = (y * 32767).astype(np.int16).tobytes()
    audio_data = sr.AudioData(pcm_bytes, sample_rate, 2)
    
    print("\n--- Method 1: Default recognize_google (sequential) ---")
    t0 = time.time()
    try:
        # Note: it will probably fail with UnknownValueError because it's just a sine wave,
        # but the API call itself will complete and we can measure the latency!
        res = sr_obj.recognize_google(audio_data, language="en-IN")
        print(f"Result: {res}")
    except sr.UnknownValueError:
        print("Got UnknownValueError (expected)")
    except Exception as e:
        print(f"Error: {e}")
    print(f"Method 1 took: {time.time() - t0:.4f}s")
    
    print("\n--- Method 2: Custom Async HTTPS Client with WAV data ---")
    # Build custom async call to Google Speech API
    client = httpx.AsyncClient()
    t0 = time.time()
    try:
        key = "AIzaSy" + "BOti4mM-6x9WDnZIjIeyEU21OpBXqWBgw"
        url = f"https://www.google.com/speech-api/v2/recognize?client=chromium&lang=en-IN&key={key}&pFilter=0"
        headers = {"Content-Type": f"audio/l16; rate={sample_rate}"}
        # In WAV/L16, the data is raw 16-bit PCM
        response = await client.post(url, content=pcm_bytes, headers=headers, timeout=10.0)
        print(f"Status Code: {response.status_code}")
        print(f"Response snippet: {response.text[:200]}")
    except Exception as e:
        print(f"Async L16 request error: {e}")
    print(f"Method 2 (L16) took: {time.time() - t0:.4f}s")
    
    print("\n--- Method 3: Custom Async HTTPS Client with FLAC data (hoping fast) ---")
    t0 = time.time()
    try:
        # Get FLAC data using speech_recognition's method (which uses flac subprocess)
        flac_data = audio_data.get_flac_data()
        key = "AIzaSy" + "BOti4mM-6x9WDnZIjIeyEU21OpBXqWBgw"
        url = f"https://www.google.com/speech-api/v2/recognize?client=chromium&lang=en-IN&key={key}&pFilter=0"
        headers = {"Content-Type": f"audio/x-flac; rate={sample_rate}"}
        response = await client.post(url, content=flac_data, headers=headers, timeout=10.0)
        print(f"Status Code: {response.status_code}")
        print(f"Response snippet: {response.text[:200]}")
    except Exception as e:
        print(f"Async FLAC request error: {e}")
    print(f"Method 3 (FLAC) took: {time.time() - t0:.4f}s")
    
    await client.aclose()

if __name__ == "__main__":
    asyncio.run(benchmark())
