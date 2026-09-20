import math
import os
import struct
import wave

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sounds", "alarm.wav")


def generate(path=OUT, seconds=10, bps=120):
    sample_rate = 22050
    frames = int(sample_rate * seconds)
    block = sample_rate // (bps // 60) // 2
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    data = bytearray()
    for i in range(frames):
        beat = (i // block) % 2
        freq = 880 if beat else 660
        envelope = min(1.0, i / (sample_rate * 0.01), (frames - i) / (sample_rate * 0.3))
        tone = math.sin(2 * math.pi * freq * i / sample_rate)
        sample = 0.35 * envelope * (0.6 + 0.4 * tone) * tone
        data += struct.pack("<h", int(sample * 32767))
    with wave.open(path, "w") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sample_rate)
        f.writeframes(bytes(data))


if __name__ == "__main__":
    generate()
    print("wrote", OUT)