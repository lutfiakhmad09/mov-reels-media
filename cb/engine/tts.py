"""TTS Gemini untuk satu episode. python3 tts.py <spec.json> <outDir>
Key dari env GEMINI_KEYS (dipisah koma). Rotasi key saat 429; kalau semua key habis untuk satu model,
SEMUA segmen dibuat ulang dengan model berikutnya supaya suara dalam satu video tetap seragam."""
import os, sys, json, base64, wave, time, shutil, urllib.request, urllib.error

MODELS = ["gemini-3.8-flash-tts", "gemini-3.1-flash-tts-preview", "gemini-3.8-flash-lite-tts", "gemini-2.5-flash-preview-tts"]
VOICE = os.environ.get("CB_VOICE", "Charon")

def call(model, key, text):
    body = json.dumps({"contents": [{"parts": [{"text": text}]}],
        "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": VOICE}}}}}).encode()
    req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent", body,
                                 {"Content-Type": "application/json", "x-goog-api-key": key})
    r = json.load(urllib.request.urlopen(req, timeout=180))
    part = next(p for p in r["candidates"][0]["content"]["parts"] if "inlineData" in p)
    return base64.b64decode(part["inlineData"]["data"])

def save(data, out):
    if data[:4] == b"RIFF": open(out, "wb").write(data); return
    with wave.open(out, "wb") as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(data)

def main():
    spec = json.load(open(sys.argv[1], encoding="utf-8")); outd = sys.argv[2]
    keys = [k.strip() for k in os.environ["GEMINI_KEYS"].split(",") if k.strip()]
    for model in MODELS:
        if os.path.isdir(outd): shutil.rmtree(outd)
        os.makedirs(outd); ki = 0; ok = True
        for seg in spec["segments"]:
            while True:
                if ki >= len(keys): ok = False; break
                try:
                    save(call(model, keys[ki], seg["vo"]), os.path.join(outd, seg["id"] + ".wav"))
                    print(f"ok {seg['id']} {model} key#{ki + 1}"); time.sleep(4); break
                except urllib.error.HTTPError as e:
                    msg = e.read()[:200]
                    if e.code in (429, 503): print(f"{e.code} {model} key#{ki + 1} -> key berikutnya"); ki += 1; continue
                    if e.code == 404: print(f"model {model} tidak tersedia"); ok = False; ki = len(keys); break
                    print(f"HTTP {e.code} {msg}"); ki += 1
                except Exception as e:
                    print("error", e); time.sleep(5); ki += 1
            if not ok: break
        if ok:
            open(os.path.join(outd, "model.txt"), "w").write(f"{model} / {VOICE}")
            print("TTS selesai:", model); return
        print(f"model {model} gagal untuk episode ini, coba model berikutnya")
    sys.exit("TTS GAGAL: semua model/key habis kuota")

if __name__ == "__main__":
    main()
