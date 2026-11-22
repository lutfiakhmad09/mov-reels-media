"""Cek balasan Telegram Mas Lutfi. "OKE" -> minggu terbaru yang sudah dikirim (NOTIFIED) tapi belum APPROVED disetujui.
"REVISI ..." -> disimpan ke REVISI.txt minggu itu (dibaca Lily di sesi berikutnya). "STOP"/"PAUSE" -> buat cb/PAUSED.
"LANJUT" -> hapus cb/PAUSED. "STATUS" -> daftar video 7 hari. "SKIP 25/11" -> lewati tanggal itu. Offset Telegram disimpan di cb/state/tg_offset.txt."""
import json, os, glob, sys, urllib.request
sys.path.insert(0, os.path.dirname(__file__))
from publish import tg_msg, TG_CHAT

ROOT = os.path.join(os.path.dirname(__file__), "..")
STATE = os.path.join(ROOT, "state", "tg_offset.txt")

def pending_week():
    weeks = sorted(glob.glob(os.path.join(ROOT, "weeks", "*")))
    for w in reversed(weeks):
        if os.path.exists(os.path.join(w, "NOTIFIED")) and not os.path.exists(os.path.join(w, "APPROVED")): return w
    return None

def main():
    off = int(open(STATE).read().strip()) if os.path.exists(STATE) else 0
    url = f"https://api.telegram.org/bot{os.environ['TG_TOKEN']}/getUpdates?timeout=0&offset={off}&allowed_updates=%5B%22message%22%5D"
    r = json.load(urllib.request.urlopen(url, timeout=60)); changed = False
    for u in r.get("result", []):
        off = max(off, u["update_id"] + 1); changed = True
        m = u.get("message") or {}
        if str((m.get("chat") or {}).get("id")) != TG_CHAT: continue
        txt = (m.get("text") or "").strip(); up = txt.upper()
        if up.startswith("OKE") or up.startswith("OK"):
            w = pending_week()
            if w:
                open(os.path.join(w, "APPROVED"), "w").write(txt); tg_msg(f"✅ Siap Mas Lutfi, minggu {os.path.basename(w)} disetujui. Video dibuat tiap subuh & tayang 18.00 WIB.")
            else: tg_msg("Tidak ada minggu yang sedang menunggu persetujuan.")
        elif up.startswith("REVISI"):
            w = pending_week() or (sorted(glob.glob(os.path.join(ROOT, "weeks", "*"))) or [None])[-1]
            if w:
                with open(os.path.join(w, "REVISI.txt"), "a", encoding="utf-8") as f: f.write(txt + "\n")
                tg_msg("📝 Catatan revisi disimpan. Lily akan menerapkannya di sesi berikutnya. Minggu ini belum dianggap OKE.")
        elif up.startswith("STATUS"):
            import datetime as dt
            today = dt.datetime.now(dt.timezone(dt.timedelta(hours=7))).date(); out = ["📋 Status CB Shorts (tayang 18.00 WIB):"]
            for sp in sorted(glob.glob(os.path.join(ROOT, "weeks", "*", "*", "spec.json"))):
                ep = os.path.dirname(sp); d = dt.date.fromisoformat(os.path.basename(ep))
                if d < today - dt.timedelta(days=1) or d > today + dt.timedelta(days=7): continue
                s_ = json.load(open(sp, encoding="utf-8")); wk = os.path.dirname(ep)
                st = "✅ terjadwal" if os.path.exists(os.path.join(ep, "DONE")) else "⏭ dilewati" if os.path.exists(os.path.join(ep, "SKIP")) else \
                     "🟢 disetujui" if os.path.exists(os.path.join(wk, "APPROVED")) else "⏳ menunggu OKE"
                out.append(f"{d.strftime('%d/%m')} {st} — {s_['yt_title']}")
            if os.path.exists(os.path.join(ROOT, "PAUSED")): out.append("⏸ Otomatisasi sedang di-STOP (balas LANJUT).")
            tg_msg("\n".join(out) if len(out) > 1 else "Belum ada video terjadwal dalam 7 hari ke depan.")
        elif up.startswith("SKIP"):
            import datetime as dt, re
            m_ = re.search(r"(\d{1,2})[/-](\d{1,2})", txt)
            if not m_: tg_msg("Format: SKIP 25/11"); continue
            yr = dt.datetime.now(dt.timezone(dt.timedelta(hours=7))).year
            d = f"{yr}-{int(m_.group(2)):02d}-{int(m_.group(1)):02d}"; hits = glob.glob(os.path.join(ROOT, "weeks", "*", d))
            if not hits: tg_msg(f"Tidak ada video tanggal {m_.group(0)}.")
            elif os.path.exists(os.path.join(hits[0], "DONE")): tg_msg(f"Video {m_.group(0)} sudah dijadwalkan di Buffer. Hapus postingannya langsung di Buffer ya.")
            else: open(os.path.join(hits[0], "SKIP"), "w").write(txt); tg_msg(f"⏭ Video {m_.group(0)} dilewati, tidak akan dibuat.")
        elif up in ("STOP", "PAUSE"):
            open(os.path.join(ROOT, "PAUSED"), "w").write("paused via telegram"); tg_msg("⏸ Produksi & posting otomatis dihentikan. Balas LANJUT untuk menyalakan lagi.")
        elif up == "LANJUT":
            p = os.path.join(ROOT, "PAUSED")
            if os.path.exists(p): os.remove(p)
            tg_msg("▶️ Produksi otomatis jalan lagi.")
    if changed:
        os.makedirs(os.path.dirname(STATE), exist_ok=True); open(STATE, "w").write(str(off))
    print("offset", off)

if __name__ == "__main__":
    main()
