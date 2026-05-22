import time
import numpy as np
import librosa

def benchmark():
    print("Generating fake audio signal...")
    sr = 16000
    duration = 5.0
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    # 220Hz sine wave
    y = np.sin(2 * np.pi * 220 * t) + np.random.normal(0, 0.1, len(t))
    
    print("Benchmarking standard features...")
    t0 = time.time()
    rms = librosa.feature.rms(y=y).mean()
    zcr = librosa.feature.zero_crossing_rate(y).mean()
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr).mean()
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    mfcc_var = np.var(mfcc, axis=1).mean()
    print(f"Standard features took: {time.time() - t0:.4f}s")
    
    print("Benchmarking default librosa.yin...")
    t0 = time.time()
    try:
        pitch = librosa.yin(y, fmin=60, fmax=500)
        pitch_valid = pitch[~np.isnan(pitch)]
        pitch_mean = np.mean(pitch_valid) if len(pitch_valid) > 0 else 200
        print(f"Default librosa.yin took: {time.time() - t0:.4f}s (pitch: {pitch_mean:.1f})")
    except Exception as e:
        print(f"Default YIN failed: {e}")

    print("Benchmarking optimized librosa.yin (hop_length=2048, frame_length=4096)...")
    t0 = time.time()
    try:
        pitch = librosa.yin(y, fmin=60, fmax=500, hop_length=2048, frame_length=4096)
        pitch_valid = pitch[~np.isnan(pitch)]
        pitch_mean = np.mean(pitch_valid) if len(pitch_valid) > 0 else 200
        print(f"Optimized YIN took: {time.time() - t0:.4f}s (pitch: {pitch_mean:.1f})")
    except Exception as e:
        print(f"Optimized YIN failed: {e}")

    print("Benchmarking optimized librosa.yin (hop_length=4096, frame_length=8192)...")
    t0 = time.time()
    try:
        pitch = librosa.yin(y, fmin=60, fmax=500, hop_length=4096, frame_length=8192)
        pitch_valid = pitch[~np.isnan(pitch)]
        pitch_mean = np.mean(pitch_valid) if len(pitch_valid) > 0 else 200
        print(f"Super-optimized YIN took: {time.time() - t0:.4f}s (pitch: {pitch_mean:.1f})")
    except Exception as e:
        print(f"Super-optimized YIN failed: {e}")

if __name__ == "__main__":
    benchmark()
