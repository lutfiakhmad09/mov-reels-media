"""Buffer + Telegram.
  publish.py buffer <spec.json> <video_url> <dueAt ISO> [--draft]   (env BUFFER_TOKEN)
  publish.py tg-video <video.mp4> <caption text>                    (env TG_TOKEN)
  publish.py tg-msg <text>"""
import json, os, sys, urllib.request, uuid

CHANNEL_ID = os.environ.get("CB_BUFFER_CHANNEL", "6b02eb028541f09ecb63b2d6")  # YouTube Budak Online
TG_CHAT = os.environ.get("CB_TG_CHAT", "1336137580")

MUTATION = """mutation CreatePost($input: CreatePostInput!) {
  createPost(input: $input) {
    __typename
    ... on PostActionSuccess { post { id status dueAt } }
    ... on MutationError { message }
  }
}"""

def buffer_post(spec, url, due, draft=False):
    inp = {"channelId": CHANNEL_ID, "text": spec["caption"], "schedulingType": "automatic",
           "assets": [{"video": {"url": url, "metadata": {"title": spec["yt_title"]}}}],
           "metadata": {"youtube": {"title": spec["yt_title"][:100], "categoryId": "2", "privacy": "public",
                                    "madeForKids": False, "isAiGenerated": True}}}
    if draft: inp["saveToDraft"] = True; inp["mode"] = "addToQueue"
    else: inp["mode"] = "customScheduled"; inp["dueAt"] = due
    body = json.dumps({"query": MUTATION, "variables": {"input": inp}}).encode()
    req = urllib.request.Request("https://api.buffer.com", body, {"Content-Type": "application/json",
                                 "Authorization": "Bearer " + os.environ["BUFFER_TOKEN"]})
    r = json.load(urllib.request.urlopen(req, timeout=120))
    print(json.dumps(r)[:800])
    cp = (r.get("data") or {}).get("createPost") or {}
    if r.get("errors") or cp.get("__typename") != "PostActionSuccess":
        raise SystemExit("BUFFER GAGAL: " + json.dumps(r)[:400])
    return cp["post"]

def _multipart(fields, files):
    b = uuid.uuid4().hex; out = b""
    for k, v in fields.items():
        out += f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
    for k, (fn, data, ct) in files.items():
        out += f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"; filename=\"{fn}\"\r\nContent-Type: {ct}\r\n\r\n".encode() + data + b"\r\n"
    return out + f"--{b}--\r\n".encode(), "multipart/form-data; boundary=" + b

def tg(method, fields, files=None):
    url = f"https://api.telegram.org/bot{os.environ['TG_TOKEN']}/{method}"
    if files:
        body, ct = _multipart(fields, files)
        req = urllib.request.Request(url, body, {"Content-Type": ct})
    else:
        req = urllib.request.Request(url, json.dumps(fields).encode(), {"Content-Type": "application/json"})
    r = json.load(urllib.request.urlopen(req, timeout=300))
    if not r.get("ok"): raise SystemExit("TELEGRAM GAGAL: " + json.dumps(r)[:300])
    return r

def tg_msg(text):
    for i in range(0, len(text), 3900): tg("sendMessage", {"chat_id": TG_CHAT, "text": text[i:i + 3900], "disable_web_page_preview": True})

def tg_video(path, caption):
    tg("sendVideo", {"chat_id": TG_CHAT, "caption": caption[:1000], "supports_streaming": "true"},
       {"video": (os.path.basename(path), open(path, "rb").read(), "video/mp4")})

if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "buffer":
        spec = json.load(open(sys.argv[2], encoding="utf-8"))
        post = buffer_post(spec, sys.argv[3], sys.argv[4], "--draft" in sys.argv)
        print("BUFFER OK", post)
    elif cmd == "tg-video": tg_video(sys.argv[2], sys.argv[3]); print("TG video ok")
    elif cmd == "tg-msg": tg_msg(sys.argv[2]); print("TG msg ok")
