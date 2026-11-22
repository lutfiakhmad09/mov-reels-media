"""Bersihkan VO (buang bunyi statis di ekor, declip), susun track VO + SFX, isi durasi segmen ke spec.
python3 audio.py <spec.json> <rawVoDir> <workDir>  -> workDir/{vo.wav,sfx.wav,spec_timed.json}"""
import json, os, sys, wave, subprocess
import numpy as np

def probe(p):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p]))

def clean(src, dst):
    w = wave.open(src); sr = w.getframerate()
    x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(float)
    fr = int(sr * 0.025); nf = len(x) // fr
    imp = np.zeros(len(x)); imp[1:-1] = np.abs(x[1:-1] - (x[:-2] + x[2:]) / 2) > 9000
    dens = np.array([imp[k * fr:(k + 1) * fr].sum() for k in range(nf)])
    hi = np.where(dens >= max(40, fr // 15))[0]; tail = hi[hi >= nf - 14]
    end = (tail[0] - 2) if len(tail) else nf
    tmp = dst + ".tmp.wav"
    with wave.open(tmp, "wb") as o:
        o.setnchannels(1); o.setsampwidth(2); o.setframerate(sr); o.writeframes(x[:max(1, end) * fr].astype(np.int16).tobytes())
    af = ("volume=-3dB,adeclip,highpass=f=80,lowpass=f=10500,"
          "silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,"
          "afade=t=in:d=0.06,areverse,afade=t=in:d=0.02,aresample=48000,apad=pad_dur=0.35")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp, "-af", af, "-ac", "1", dst], check=True)
    os.remove(tmp)

def sfx(spec, out, sr=48000):
    segs = spec["segments"]; T = sum(s["dur"] for s in segs); n = int(T * sr) + sr
    o = np.zeros(n); rng = np.random.default_rng(1)
    def add(sig, at, g=1.0):
        i = max(0, int(at * sr)); e = min(n, i + len(sig)); o[i:e] += g * sig[:e - i]
    m = int(0.35 * sr); env = np.sin(np.linspace(0, np.pi, m)) ** 2
    wh = np.convolve(rng.standard_normal(m), np.ones(12) / 12, "same") * env; wh = wh / np.abs(wh).max() * 0.5
    m = int(0.09 * sr); tt = np.arange(m) / sr; pp = np.sin(2 * np.pi * np.cumsum(np.linspace(900, 300, m)) / sr) * np.exp(-tt * 35) * 0.45
    m = int(0.6 * sr); tt = np.arange(m) / sr; dg = (np.sin(2 * np.pi * 1320 * tt) + 0.5 * np.sin(2 * np.pi * 1980 * tt)) * np.exp(-tt * 6) * 0.3
    rainmask = np.zeros(n); t0 = 0
    for s in segs:
        for b in s["beats"]:
            at = t0 + b.get("at", 0) * s["dur"]
            if at > 0.2: add(wh, at - 0.12, 0.9)
            add(pp, at + 0.05, 0.8)
            if b["scene"] in ("lever", "checklist", "mythfact", "cta"): add(dg, at + min(1.5, 0.75 * s["dur"]))
            if b.get("rain") or b["scene"] in ("hero", "hero_alert", "cta"):
                rainmask[int(at * sr):int((t0 + s["dur"]) * sr)] = 1
        t0 += s["dur"]
    rainmask = np.convolve(rainmask, np.ones(sr // 4) / (sr // 4), "same")
    o += np.convolve(rng.standard_normal(n), np.ones(6) / 6, "same") * 0.05 * rainmask
    o = np.clip(o[:int(T * sr)], -0.95, 0.95)
    with wave.open(out, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes((o * 32767).astype(np.int16).tobytes())

def main():
    spec = json.load(open(sys.argv[1], encoding="utf-8")); raw, work = sys.argv[2], sys.argv[3]
    os.makedirs(work, exist_ok=True); lst = os.path.join(work, "list.txt")
    with open(lst, "w") as L:
        for s in spec["segments"]:
            dst = os.path.join(work, s["id"] + ".wav"); clean(os.path.join(raw, s["id"] + ".wav"), dst)
            s["dur"] = round(probe(dst), 3); L.write(f"file '{os.path.abspath(dst)}'\n")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst,
                    "-af", "loudnorm=I=-16:TP=-2:LRA=9,alimiter=limit=0.85", "-ar", "48000", os.path.join(work, "vo.wav")], check=True)
    sfx(spec, os.path.join(work, "sfx.wav"))
    json.dump(spec, open(os.path.join(work, "spec_timed.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print("audio ok, total", round(sum(s["dur"] for s in spec["segments"]), 2), "detik")

if __name__ == "__main__":
    main()
