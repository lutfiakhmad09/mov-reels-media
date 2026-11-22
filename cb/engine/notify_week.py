"""Kirim daftar naskah minggu baru ke Telegram untuk disetujui (sekali per minggu, tandai NOTIFIED)."""
import glob, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from publish import tg_msg
ROOT = os.path.join(os.path.dirname(__file__), "..")
HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]

def main():
    import datetime as dt
    for w in sorted(glob.glob(os.path.join(ROOT, "weeks", "*"))):
        if os.path.exists(os.path.join(w, "NOTIFIED")) or not os.path.exists(os.path.join(w, "READY")): continue
        lines = [f"🏍️ Naskah CB Shorts minggu {os.path.basename(w)} (tayang 18.00 WIB)\n"]
        note = os.path.join(w, "research.md")
        for sp in sorted(glob.glob(os.path.join(w, "*", "spec.json"))):
            s = json.load(open(sp, encoding="utf-8")); d = dt.date.fromisoformat(s["date"])
            lines.append(f"#{s.get('no', '')} {HARI[d.weekday()]} {d.strftime('%d/%m')} — {s['yt_title']}")
            lines.append("   Hook: " + s["segments"][0]["vo"])
            lines.append("   Isi: " + " ".join(seg["vo"] for seg in s["segments"][1:-1])[:300] + "\n")
        if os.path.exists(note): lines.append("📈 Riset tren:\n" + open(note, encoding="utf-8").read()[:900] + "\n")
        lines.append("Balas OKE kalau setuju, atau REVISI #nomor: catatan. Tanpa OKE, video minggu ini tidak dibuat.")
        tg_msg("\n".join(lines)); open(os.path.join(w, "NOTIFIED"), "w").write("ok"); print("notified", w)

if __name__ == "__main__":
    main()
