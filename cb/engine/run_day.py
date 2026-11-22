"""Pipeline harian. python3 run_day.py [YYYY-MM-DD] [--dry]
--dry: tidak menjadwalkan ke Buffer (cuma draft-test) & video dikirim ke Telegram berlabel TES.
Butuh env GEMINI_KEYS, BUFFER_TOKEN, TG_TOKEN. Dijalankan dari root repo."""
import datetime as dt, glob, json, os, shutil, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
from publish import tg_msg, tg_video, buffer_post

POST_HOUR = os.environ.get("CB_POST_TIME", "18:00")
REPO_RAW = "https://raw.githubusercontent.com/lutfiakhmad09/mov-reels-media/main/"

def sh(*a): print("+", " ".join(a)); subprocess.run(a, check=True)

def git_push(paths, msg):
    sh("git", "add", *paths)
    if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode == 0: return
    sh("git", "commit", "-m", msg)
    for _ in range(4):
        if subprocess.run(["git", "pull", "--rebase", "-X", "theirs", "origin", "main"]).returncode == 0 and \
           subprocess.run(["git", "push", "origin", "HEAD:main"]).returncode == 0: return
    raise SystemExit("git push gagal")

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]; dry = "--dry" in sys.argv
    today = args[0] if args else dt.datetime.now(dt.timezone(dt.timedelta(hours=7))).strftime("%Y-%m-%d")
    if os.path.exists(os.path.join(ROOT, "PAUSED")) and not dry: print("PAUSED"); return
    found = glob.glob(os.path.join(ROOT, "weeks", "*", today, "spec.json"))
    if not found: tg_msg(f"⚠️ CB Shorts {today}: belum ada naskah untuk hari ini. Tidak ada video yang dibuat."); return
    ep = os.path.dirname(found[0]); week = os.path.dirname(ep)
    if not dry and not os.path.exists(os.path.join(week, "APPROVED")):
        tg_msg(f"⏳ CB Shorts {today}: minggu {os.path.basename(week)} belum di-OKE-kan, video hari ini tidak dibuat. Balas OKE kalau naskahnya sudah sesuai."); return
    vid_rel = f"cb/videos/{today}.mp4"; vid = os.path.join(ROOT, "videos", f"{today}.mp4")
    if os.path.exists(os.path.join(ep, "DONE")) and not dry: print("sudah selesai"); return
    work = os.path.join("/tmp", "cbwork", today); shutil.rmtree(work, ignore_errors=True); os.makedirs(work)
    spec = os.path.join(ep, "spec.json")
    sh("python3", os.path.join(HERE, "tts.py"), spec, os.path.join(work, "raw"))
    sh("python3", os.path.join(HERE, "audio.py"), spec, os.path.join(work, "raw"), work)
    if os.path.exists(os.path.join(ep, "hero.png")): shutil.copy(os.path.join(ep, "hero.png"), os.path.join(work, "hero.png"))
    out = os.path.join(work, "video.mp4")
    sh("python3", os.path.join(HERE, "render.py"), os.path.join(work, "spec_timed.json"), out, os.path.join(work, "vo.wav"), os.path.join(work, "sfx.wav"))
    S = json.load(open(spec, encoding="utf-8")); model = open(os.path.join(work, "raw", "model.txt")).read().strip()
    if dry:
        tg_video(out, f"🧪 TES pipeline CB Shorts ({today})\n{S['yt_title']}\nVO: {model}\n(Tidak dijadwalkan ke YouTube)")
        if "--buffer-test" in sys.argv:
            post = buffer_post(S, "https://raw.githubusercontent.com/lutfiakhmad09/mov-reels-media/cb-shorts/videos/cb/cb-copbusi-brebet-hujan.mp4", "", draft=True)
            tg_msg(f"🧪 Tes Buffer OK: draft dibuat (id {post.get('id')}, status {post.get('status')}). Draft ini tidak tayang, boleh dihapus di Buffer.")
        print("dry run selesai"); return
    os.makedirs(os.path.dirname(vid), exist_ok=True); shutil.copy(out, vid)
    git_push([vid_rel], f"cb: video {today}")
    due = f"{today}T{POST_HOUR}:00+07:00"
    post = buffer_post(S, REPO_RAW + vid_rel, due)
    open(os.path.join(ep, "DONE"), "w").write(json.dumps(post))
    git_push([os.path.relpath(os.path.join(ep, "DONE"), os.path.join(ROOT, ".."))], f"cb: done {today}")
    tg_video(out, f"✅ Video {today} sudah dijadwalkan di Buffer → YouTube Budak Online jam {POST_HOUR} WIB\n\n{S['yt_title']}\n\nVO: {model}\nKalau ada yang salah, hapus/ubah postingannya di Buffer sebelum jam tayang. Balas STOP untuk menghentikan otomatisasi.")

if __name__ == "__main__":
    try: main()
    except SystemExit as e:
        if e.code not in (None, 0):
            try: tg_msg(f"❌ CB Shorts gagal: {e.code}\nCek tab Actions di GitHub mov-reels-media.")
            except Exception: pass
        raise
    except Exception as e:
        try: tg_msg(f"❌ CB Shorts error: {e}\nCek tab Actions di GitHub mov-reels-media.")
        except Exception: pass
        raise
