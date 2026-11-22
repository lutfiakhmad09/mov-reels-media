# CB Shorts – otomatisasi harian (YouTube Budak Online)

Alur:
1. **Minggu** – Lily (scheduled task Claude) riset tren konten motor yang lagi viral, menulis 7 naskah
   `cb/weeks/<YYYY-Www>/<tanggal>/spec.json` + `hero.png` (gambar AI Canva), lalu membuat file `READY`.
2. **cb-approval.yml** (tiap 30 menit) – kirim daftar naskah ke Telegram Mas Lutfi (`NOTIFIED`), baca balasan:
   `OKE` → `APPROVED` · `REVISI #n: ...` → `REVISI.txt` · `STOP` → `cb/PAUSED` · `LANJUT` → hapus PAUSED · `STATUS` → daftar 7 hari · `SKIP 25/11` → lewati tanggal itu.
3. **cb-daily.yml** (05:07 WIB) – episode hari ini: TTS Gemini (rotasi `GEMINI_KEYS`, ganti model kalau kuota habis),
   bersihkan audio, render (`engine/render.py`), simpan `cb/videos/<tanggal>.mp4`, jadwalkan di Buffer jam 18.00 WIB,
   kirim video ke Telegram.

Secret (Settings → Secrets → Actions): `GEMINI_KEYS`, `BUFFER_TOKEN`, `TG_TOKEN`. Tidak ada key di repo ini.
Tes manual: Actions → "CB Shorts - produksi harian" → Run workflow (dry = tidak dijadwalkan ke YouTube).

Format spec: lihat `weeks/2026-W48/2026-11-23/spec.json`; daftar scene ada di `engine/render.py` (SCENES).
Font Poppins (SIL Open Font License 1.1, Indian Type Foundry).
