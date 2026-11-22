"""Engine render Shorts otomotif (spec-driven).
Usage: python3 render.py <spec.json> <out.mp4> [vo.wav] [sfx.wav] [--stills t1,t2,...]
spec.segments[i] = {id, vo, dur (detik, diisi audio.py), beats:[{at:0..1, scene:..., ...params}]}
Scene yang tersedia: lihat SCENES di bawah. Hero image: hero.png di folder spec (opsional)."""
import json, math, random, subprocess, sys, os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS = 1080, 1920, 30
FD = "/usr/share/fonts/truetype"
def _font(names):
    for n in names:
        for root, _, files in os.walk("/usr/share/fonts"):
            if n in files: return os.path.join(root, n)
    here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
    for n in names:
        if os.path.exists(os.path.join(here, n)): return os.path.join(here, n)
    raise SystemExit("font tidak ditemukan: " + str(names))
FB = _font(["Poppins-Bold.ttf", "DejaVuSans-Bold.ttf"])
FM = _font(["Poppins-Medium.ttf", "DejaVuSans.ttf"])
_fc = {}
def F(s, b=True):
    s = max(8, int(s)); k = (s, b)
    if k not in _fc: _fc[k] = ImageFont.truetype(FB if b else FM, s)
    return _fc[k]

BG1, BG2 = (10, 16, 30), (24, 38, 70)
COL = {"orange": (255, 122, 26), "yellow": (255, 214, 64), "red": (235, 64, 52), "green": (60, 200, 110),
       "white": (245, 247, 250), "blue": (90, 170, 255), "mud": (120, 84, 50), "steel": (150, 158, 170)}
def C(c): return COL.get(c, c) if isinstance(c, str) else tuple(c)
ORANGE, YELLOW, RED, GREEN, WHITE, BLUE, MUD, STEEL = [COL[k] for k in ("orange", "yellow", "red", "green", "white", "blue", "mud", "steel")]

def ease(x): x = max(0, min(1, x)); return 1 - (1 - x) ** 3
def pop(x):
    x = max(0, min(1, x)); c = 1.7
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2
def lerp(a, b, k): return a + (b - a) * k
def rng2(v, k):  # v bisa angka atau [a,b]
    return lerp(v[0], v[1], k) if isinstance(v, (list, tuple)) else v

# ---------- assets ----------
bg = Image.new("RGB", (W, H)); _bd = ImageDraw.Draw(bg)
for y in range(H):
    k = y / H; _bd.line([(0, y), (W, y)], fill=tuple(int(BG1[i] + (BG2[i] - BG1[i]) * k) for i in range(3)))
bg = bg.convert("RGBA")
grad = Image.new("RGBA", (W, H), (0, 0, 0, 0)); _gd = ImageDraw.Draw(grad)
for y in range(H):
    a = int(200 * max(0, (y - H * 0.45) / (H * 0.55)) ** 1.2) + int(130 * max(0, (H * 0.25 - y) / (H * 0.25)))
    _gd.line([(0, y), (W, y)], fill=(0, 0, 0, min(230, a)))
random.seed(3)
RAIN = [(random.uniform(0, W), random.uniform(0, H), random.uniform(1100, 1700), random.uniform(40, 100)) for _ in range(130)]
PART = [(random.uniform(-1, 1), random.uniform(0, 1), random.random()) for _ in range(70)]
HERO = HERO_BLUR = None

# ---------- primitives ----------
def text_c(d, xy, s, f, fill=WHITE, stroke=0, sf=(0, 0, 0), anchor="mm"):
    d.text(xy, s, font=f, fill=fill, anchor=anchor, stroke_width=stroke, stroke_fill=sf)

def fit_size(d, lines, size, maxw=980):
    for ln in lines:
        while size > 30 and d.textlength(ln, font=F(size)) > maxw: size -= 4
    return size

def title(d, lines, lt, color=WHITE, y=250, size=100, start=0.0, instant=False):
    if not lines: return
    if isinstance(lines, str): lines = [lines]
    k = 1.0 if instant else pop((lt - start) / 0.3)
    if k <= 0: return
    size = fit_size(d, lines, size)
    for i, ln in enumerate(lines):
        text_c(d, (W // 2, y + i * int(size * 1.08)), ln, F(size * k), fill=C(color), stroke=8)

def pill(d, xy, s, bgc, fg=(15, 15, 20), size=54, k=1.0):
    if k <= 0 or not s: return
    f = F(size * k); bb = d.textbbox(xy, s, font=f, anchor="mm")
    d.rounded_rectangle((bb[0] - 28, bb[1] - 16, bb[2] + 28, bb[3] + 16), 40, fill=C(bgc))
    text_c(d, xy, s, f, fill=C(fg))

def rain(d, t, a=130):
    for x, y0, sp, ln in RAIN:
        y = (y0 + t * sp) % (H + 200) - 100
        d.line([(x, y), (x - ln * 0.2, y + ln)], fill=(170, 200, 255, a), width=3)

def check(d, cx, cy, r, col=GREEN):
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=C(col))
    d.line([(cx - r * 0.45, cy), (cx - r * 0.1, cy + r * 0.38), (cx + r * 0.5, cy - r * 0.35)], fill=WHITE, width=int(r * 0.22), joint="curve")

def cross(d, cx, cy, r, col=RED):
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=C(col)); q = r * 0.42
    d.line([(cx - q, cy - q), (cx + q, cy + q)], fill=WHITE, width=int(r * 0.22))
    d.line([(cx - q, cy + q), (cx + q, cy - q)], fill=WHITE, width=int(r * 0.22))

def arrow(d, a, b, col, w=10):
    col = C(col); d.line([a, b], fill=col, width=w); ang = math.atan2(b[1] - a[1], b[0] - a[0])
    d.polygon([b, (b[0] - 34 * math.cos(ang - 0.45), b[1] - 34 * math.sin(ang - 0.45)),
               (b[0] - 34 * math.cos(ang + 0.45), b[1] - 34 * math.sin(ang + 0.45))], fill=col)

def label(d, s, tip, at, col=ORANGE, k=1.0):
    if k <= 0: return
    arrow(d, at, tip, col, 8); pill(d, at, s, col, size=46, k=k)

def warn(d, cx, cy, r, col=YELLOW):
    d.polygon([(cx, cy - r), (cx + r * 1.05, cy + r * 0.8), (cx - r * 1.05, cy + r * 0.8)], fill=C(col), outline=(20, 20, 20), width=6)
    text_c(d, (cx, cy + r * 0.2), "!", F(r * 1.1), fill=(20, 20, 20))

# ---------- illustrations ----------
def wheel(d, cx, cy, R, ang):
    d.ellipse((cx - R, cy - R, cx + R, cy + R), fill=(22, 22, 26))
    for i in range(24):
        a = ang + i * math.pi / 12
        d.line([(cx + R * 0.93 * math.cos(a), cy + R * 0.93 * math.sin(a)), (cx + R * math.cos(a), cy + R * math.sin(a))], fill=(55, 55, 60), width=10)
    r2 = R * 0.78
    d.ellipse((cx - r2, cy - r2, cx + r2, cy + r2), outline=(200, 205, 215), width=max(4, int(R * 0.032)))
    d.ellipse((cx - r2 + 14, cy - r2 + 14, cx + r2 - 14, cy + r2 - 14), fill=(28, 32, 44))
    for i in range(18):
        a = ang + i * math.pi / 9
        d.line([(cx + R * 0.2 * math.cos(a), cy + R * 0.2 * math.sin(a)), (cx + r2 * math.cos(a + 0.3), cy + r2 * math.sin(a + 0.3))], fill=(190, 195, 205), width=4)
    rh = R * 0.24
    d.ellipse((cx - rh, cy - rh, cx + rh, cy + rh), fill=(120, 126, 136), outline=(210, 214, 222), width=6)

def drum(img, cx, cy, R, ang, expand=0.0, heat=0.0, water=0.0, mud=0.0, t=0.0, cracks=0.0):
    d = ImageDraw.Draw(img)
    d.ellipse((cx - R, cy - R, cx + R, cy + R), fill=(70, 74, 84))
    d.ellipse((cx - R * 0.9, cy - R * 0.9, cx + R * 0.9, cy + R * 0.9), fill=(20, 22, 28))
    for i in range(36):
        a = ang + i * math.pi / 18
        d.line([(cx + R * 0.91 * math.cos(a), cy + R * 0.91 * math.sin(a)), (cx + R * 0.99 * math.cos(a), cy + R * 0.99 * math.sin(a))], fill=(110, 114, 124), width=4)
    rin = R * 0.9; gap = R * 0.09 * (1 - expand)
    ro = rin - gap - 2; rl = ro - R * 0.11; rs = rl - R * 0.06
    for a0, a1 in ((105, 255), (-75, 75)):
        d.arc((cx - ro, cy - ro, cx + ro, cy + ro), a0, a1, fill=(176, 96, 48), width=int(ro - rl))
        d.arc((cx - rl, cy - rl, cx + rl, cy + rl), a0, a1, fill=STEEL, width=int(rl - rs))
        for j in range(int(6 * cracks)):
            a = math.radians(lerp(a0 + 15, a1 - 15, j / 5)); rr = (ro + rl) / 2
            d.line([(cx + (rr - 18) * math.cos(a), cy + (rr - 18) * math.sin(a)), (cx + (rr + 6) * math.cos(a + 0.04), cy + (rr + 6) * math.sin(a + 0.04)), (cx + (rr + 18) * math.cos(a - 0.03), cy + (rr + 18) * math.sin(a - 0.03))], fill=(40, 20, 10), width=4)
    for sgn in (-1, 1):
        y = cy + sgn * rs * 0.82
        d.line([(cx - rs * 0.45 + j * rs * 0.09, y + (10 if j % 2 else -10)) for j in range(11)], fill=(200, 200, 90), width=5)
    cw = R * 0.16; ca = 0.6 * expand
    d.polygon([(cx + cw * math.cos(ca + k * math.pi / 2 + math.pi / 4), cy + cw * 0.55 * math.sin(ca + k * math.pi / 2 + math.pi / 4)) for k in range(4)], fill=(210, 214, 222))
    d.ellipse((cx - 22, cy - 22, cx + 22, cy + 22), fill=(90, 94, 104))
    if heat > 0:
        g = Image.new("RGBA", img.size, (0, 0, 0, 0)); g2 = ImageDraw.Draw(g)
        for a0, a1 in ((115, 245), (-65, 65)):
            g2.arc((cx - rin - 4, cy - rin - 4, cx + rin + 4, cy + rin + 4), a0, a1, fill=(255, 140, 30, int(220 * heat)), width=26)
        img.alpha_composite(g.filter(ImageFilter.GaussianBlur(10))); d = ImageDraw.Draw(img)
    if water > 0:
        g = Image.new("RGBA", img.size, (0, 0, 0, 0)); ImageDraw.Draw(g).ellipse((cx - rin, cy - rin, cx + rin, cy + rin), outline=(90, 170, 255, int(200 * water)), width=int(14 + 10 * water))
        img.alpha_composite(g); d = ImageDraw.Draw(img)
        for (px, py, ph) in PART:
            if ph > water: continue
            a = px * math.pi + t * 1.5; rr = rin * (0.55 + 0.4 * ((py + t * 0.6) % 1))
            x, y = cx + rr * math.cos(a), cy + rr * math.sin(a)
            d.ellipse((x - 9, y - 12, x + 9, y + 9), fill=MUD if ph < mud else BLUE)

def plug(d, cx, cy, s, t, flow=0.0, crack=0.0, water=0.0, spark=1.0, broken=False):
    """Koil -> kabel -> cop busi -> busi. cx,cy = tengah busi; s = skala (1 = ~600px tinggi)."""
    def P(x, y): return (cx + x * s, cy + y * s)
    coil = (P(-390, -470), P(-180, -340))
    d.rounded_rectangle((coil[0][0], coil[0][1], coil[1][0], coil[1][1]), int(18 * s), fill=(60, 66, 80), outline=(120, 130, 150), width=4)
    text_c(d, ((coil[0][0] + coil[1][0]) / 2, (coil[0][1] + coil[1][1]) / 2), "KOIL", F(44 * s), fill=WHITE)
    cable = [P(-180, -405), P(-100, -395), P(-30, -340), P(0, -260), P(0, -200)]
    d.line(cable, fill=(20, 20, 22), width=int(26 * s), joint="curve")
    d.rounded_rectangle((*P(-35, -20), *P(35, 112)), int(10 * s), fill=(236, 236, 230))
    d.polygon([P(-62, 112), P(62, 112), P(72, 136), P(62, 162), P(-62, 162), P(-72, 136)], fill=(170, 176, 186))
    d.rectangle((*P(-28, 162), *P(28, 260)), fill=(150, 156, 166))
    for yy in range(168, 260, 12): d.line([P(-28, yy), P(28, yy + 6)], fill=(105, 110, 120), width=3)
    d.rectangle((*P(-5, 260), *P(5, 286)), fill=(190, 190, 190))
    d.line([P(20, 260), P(20, 296), P(6, 296)], fill=(160, 160, 160), width=7)
    d.rounded_rectangle((*P(-75, -200), *P(75, 5)), int(40 * s), fill=(38, 38, 42), outline=(80, 80, 88), width=4)
    for yy in (-140, -100, -60): d.line([P(-63, yy), P(63, yy)], fill=(70, 70, 78), width=6)
    if crack > 0:
        pts = [P(-58, -165), P(-35, -140), P(-48, -110), P(-20, -85), P(-33, -52), P(-8, -28)]
        n = max(2, int(len(pts) * crack + 0.999)); d.line(pts[:n], fill=RED, width=9, joint="curve")
    if water > 0:
        for j in range(6):
            ph = (t * 0.9 + j / 6) % 1
            x = cx + (-300 * (1 - ph) - 60) * s; y = cy + (-360 + ph * 260) * s
            if ph < water + 0.2: d.ellipse((x - 16, y - 22, x + 16, y + 16), fill=BLUE)
    if flow > 0:
        path = cable + [P(0, -200), P(0, 5), P(0, 112), P(0, 260), P(0, 290)]
        pts = []
        for i in range(len(path) - 1):
            for j in range(20): pts.append((lerp(path[i][0], path[i + 1][0], j / 20), lerp(path[i][1], path[i + 1][1], j / 20)))
        for k in range(7):
            if broken and random.random() < 0.55: continue
            x, y = pts[int((t * 140 + k * len(pts) / 7) % len(pts))]
            d.ellipse((x - 11, y - 11, x + 11, y + 11), fill=YELLOW)
    if spark > 0 and (not broken or random.random() < 0.3):
        r = (24 + 8 * math.sin(t * 20)) * s * spark; x, y = P(0, 302)
        d.polygon([(x + (r if i % 2 == 0 else r * 0.42) * math.cos(i * math.pi / 8), y + (r if i % 2 == 0 else r * 0.42) * math.sin(i * math.pi / 8)) for i in range(16)], fill=YELLOW)

def chain(d, cx, cy, s, t, rust=0.0, oil=0.0, slack=0.0):
    """Gir depan kecil (kiri) & gir belakang besar (kanan) dengan rantai."""
    r1, r2 = 110 * s, 230 * s; x1, x2 = cx - 300 * s, cx + 200 * s
    for (x, r, sp) in ((x1, r1, 2.0), (x2, r2, 2.0 * r1 / r2)):
        d.ellipse((x - r, cy - r, x + r, cy + r), fill=(150, 156, 166))
        for i in range(int(r / 12)):
            a = t * sp + i * 2 * math.pi / int(r / 12)
            d.polygon([(x + r * math.cos(a - 0.08), cy + r * math.sin(a - 0.08)), (x + (r + 16 * s) * math.cos(a), cy + (r + 16 * s) * math.sin(a)), (x + r * math.cos(a + 0.08), cy + r * math.sin(a + 0.08))], fill=(150, 156, 166))
        d.ellipse((x - r * 0.35, cy - r * 0.35, x + r * 0.35, cy + r * 0.35), fill=(70, 74, 84))
    sag = 50 * s * slack
    top = [(lerp(x1, x2, k), cy - lerp(r1, r2, k) - 14 * s) for k in [i / 30 for i in range(31)]]
    bot = [(lerp(x1, x2, k), cy + lerp(r1, r2, k) + 14 * s + sag * math.sin(math.pi * k)) for k in [i / 30 for i in range(31)]]
    col = (lerp(60, 150, rust), lerp(62, 70, rust), lerp(70, 30, rust))
    col = tuple(int(c) for c in col)
    for line in (top, bot):
        d.line(line, fill=col, width=int(22 * s))
        for i, (x, y) in enumerate(line):
            if (i + int(t * 10)) % 2: d.ellipse((x - 6 * s, y - 6 * s, x + 6 * s, y + 6 * s), fill=(200, 200, 205) if rust < 0.5 else (170, 90, 40))
    if oil > 0:
        for j in range(5):
            ph = (t * 0.8 + j / 5) % 1; x = lerp(x1, x2, 0.3 + j * 0.1); y = cy - 400 * s + ph * 230 * s
            if ph < oil + 0.1: d.ellipse((x - 12, y - 16, x + 12, y + 12), fill=(230, 180, 40))

def piston(d, cx, cy, s, t, stage=None):
    """Mesin 4-tak sederhana; stage 0..3 (hisap, kompresi, usaha, buang) atau None = jalan terus."""
    ph = (t * 0.5) % 1 if stage is None else (stage + 0.5) / 4
    ang = ph * 4 * math.pi; ypos = 120 * s * math.cos(ang)
    d.rectangle((cx - 170 * s, cy - 420 * s, cx + 170 * s, cy + 220 * s), outline=(150, 156, 166), width=int(14 * s))
    py = cy - 120 * s - ypos
    d.rectangle((cx - 150 * s, py - 70 * s, cx + 150 * s, py + 70 * s), fill=(170, 176, 186))
    for k in range(3): d.line([(cx - 150 * s, py - 50 * s + k * 18 * s), (cx + 150 * s, py - 50 * s + k * 18 * s)], fill=(90, 94, 104), width=4)
    ccx, ccy = cx, cy + 330 * s; cr = 120 * s
    px_, py_ = ccx + cr * math.sin(ang), ccy - cr * math.cos(ang)
    d.ellipse((ccx - 150 * s, ccy - 150 * s, ccx + 150 * s, ccy + 150 * s), outline=(110, 114, 124), width=int(10 * s))
    d.line([(cx, py), (px_, py_)], fill=(200, 204, 212), width=int(30 * s))
    d.ellipse((px_ - 26 * s, py_ - 26 * s, px_ + 26 * s, py_ + 26 * s), fill=(220, 224, 232))
    st = int(ph * 4) % 4
    names = ["HISAP", "KOMPRESI", "USAHA", "BUANG"]; cols = [BLUE, YELLOW, RED, STEEL]
    if st == 0: d.rectangle((cx - 140 * s, cy - 410 * s, cx + 140 * s, py - 72 * s), fill=(90, 170, 255, 110))
    if st == 1: d.rectangle((cx - 140 * s, cy - 410 * s, cx + 140 * s, py - 72 * s), fill=(255, 214, 64, 110))
    if st == 2:
        d.rectangle((cx - 140 * s, cy - 410 * s, cx + 140 * s, py - 72 * s), fill=(255, 100, 40, 150))
        text_c(d, (cx, cy - 380 * s), "*", F(120 * s), fill=YELLOW)
    if st == 3: d.rectangle((cx - 140 * s, cy - 410 * s, cx + 140 * s, py - 72 * s), fill=(120, 120, 130, 130))
    pill(d, (cx, cy + 560 * s), f"{st + 1}. {names[st]}", cols[st], size=60 * s)

def gauge(d, cx, cy, r, v, txt=None):
    for col, a0, a1 in ((RED, 180, 240), (YELLOW, 240, 300), (GREEN, 300, 360)):
        d.arc((cx - r, cy - r, cx + r, cy + r), a0, a1, fill=col, width=max(12, int(r * 0.12)))
    a = math.radians(180 + 180 * max(0, min(1, v)))
    d.line([(cx, cy), (cx + (r - 40) * math.cos(a), cy + (r - 40) * math.sin(a))], fill=WHITE, width=12)
    d.ellipse((cx - 22, cy - 22, cx + 22, cy + 22), fill=WHITE)
    if txt: text_c(d, (cx, cy + 70), txt, F(46), fill=WHITE, stroke=4)

def lever(d, cx, cy, press):
    d.rounded_rectangle((cx - 380, cy - 22, cx + 120, cy + 22), 20, fill=(60, 62, 70))
    d.rounded_rectangle((cx + 60, cy - 46, cx + 260, cy + 46), 30, fill=(25, 25, 28))
    a = math.radians(14 - 14 * press); px, py = cx - 300, cy + 40
    d.line([(px, py), (px + 420 * math.cos(a), py + 420 * math.sin(a) + 30)], fill=(200, 204, 212), width=26)
    d.ellipse((px - 26, py - 26, px + 26, py + 26), fill=(120, 124, 134))

def icon(d, name, cx, cy, s, t):
    if name == "house":
        d.polygon([(cx - s, cy), (cx, cy - s * 0.8), (cx + s, cy)], fill=ORANGE)
        d.rectangle((cx - s * 0.75, cy, cx + s * 0.75, cy + s * 0.9), fill=WHITE)
        d.rectangle((cx - s * 0.18, cy + s * 0.4, cx + s * 0.18, cy + s * 0.9), fill=(120, 80, 50))
    elif name == "bucket":
        d.polygon([(cx - s, cy - s * 0.6), (cx + s, cy - s * 0.6), (cx + s * 0.75, cy + s * 0.7), (cx - s * 0.75, cy + s * 0.7)], fill=BLUE)
        d.ellipse((cx - s, cy - s * 0.75, cx + s, cy - s * 0.45), fill=(150, 200, 255))
        for i in range(6):
            ph = (t * 0.8 + i / 6) % 1; x = cx - s * 0.6 + i * s * 0.25 + 20 * math.sin(t * 3 + i); y = cy - s * 0.7 - ph * s * 1.4; r = 10 + 14 * ph
            d.ellipse((x - r, y - r, x + r, y + r), outline=(220, 240, 255), width=4)
    elif name == "wrench":
        a = -0.6 + 0.4 * math.sin(t * 6); ca, sa = math.cos(a), math.sin(a)
        def R_(x, y): return (cx + x * ca - y * sa, cy + x * sa + y * ca)
        d.line([R_(-s, 0), R_(s * 0.7, 0)], fill=STEEL, width=int(s * 0.28))
        hx, hy = R_(s * 0.7, 0); d.ellipse((hx - s * 0.32, hy - s * 0.32, hx + s * 0.32, hy + s * 0.32), fill=STEEL)
        hx, hy = R_(s * 0.9, 0); d.ellipse((hx - s * 0.14, hy - s * 0.14, hx + s * 0.14, hy + s * 0.14), fill=BG2)
    elif name == "garage":
        d.polygon([(cx - s, cy - s * 0.3), (cx, cy - s), (cx + s, cy - s * 0.3)], fill=BLUE)
        d.rectangle((cx - s * 0.85, cy - s * 0.3, cx + s * 0.85, cy + s * 0.8), fill=(60, 66, 80))
        for i in range(5): d.rectangle((cx - s * 0.6, cy - s * 0.1 + i * s * 0.18, cx + s * 0.6, cy - s * 0.1 + i * s * 0.18 + s * 0.12), fill=(170, 176, 190))
    elif name == "wheel": wheel(d, cx, cy, s, t * 2)
    elif name == "soundwave":
        for i in range(3):
            r = s * (0.4 + i * 0.3) + 20 * math.sin(t * 10 + i); d.arc((cx - r, cy - r, cx + r, cy + r), -40, 40, fill=YELLOW, width=10)
    elif name == "warn": warn(d, cx, cy, s)
    elif name == "check": check(d, cx, cy, s)
    elif name == "cross": cross(d, cx, cy, s)
    elif name == "drop":
        d.polygon([(cx, cy - s), (cx + s * 0.6, cy + s * 0.2), (cx - s * 0.6, cy + s * 0.2)], fill=BLUE); d.ellipse((cx - s * 0.6, cy - s * 0.25, cx + s * 0.6, cy + s * 0.75), fill=BLUE)
    elif name == "oil":
        d.rounded_rectangle((cx - s * 0.7, cy - s * 0.5, cx + s * 0.5, cy + s * 0.7), int(s * 0.15), fill=(230, 180, 40))
        d.line([(cx + s * 0.5, cy - s * 0.3), (cx + s, cy - s * 0.7)], fill=(230, 180, 40), width=int(s * 0.2))
        text_c(d, (cx - s * 0.1, cy + s * 0.1), "OLI", F(s * 0.45), fill=(40, 30, 10))
    elif name == "fuel":
        d.rounded_rectangle((cx - s * 0.6, cy - s * 0.8, cx + s * 0.4, cy + s * 0.8), int(s * 0.15), fill=RED)
        d.rectangle((cx - s * 0.4, cy - s * 0.6, cx + s * 0.2, cy - s * 0.1), fill=WHITE)
        d.line([(cx + s * 0.4, cy - s * 0.3), (cx + s * 0.75, cy), (cx + s * 0.75, cy + s * 0.6)], fill=STEEL, width=int(s * 0.12))
    elif name == "battery":
        d.rounded_rectangle((cx - s, cy - s * 0.6, cx + s, cy + s * 0.7), int(s * 0.1), fill=(40, 44, 54), outline=STEEL, width=6)
        d.rectangle((cx - s * 0.7, cy - s * 0.85, cx - s * 0.35, cy - s * 0.6), fill=RED); d.rectangle((cx + s * 0.35, cy - s * 0.85, cx + s * 0.7, cy - s * 0.6), fill=STEEL)
        lvl = 0.5 + 0.5 * math.sin(t * 2)
        d.rectangle((cx - s * 0.8, cy + s * 0.5 - s * 0.9 * lvl, cx + s * 0.8, cy + s * 0.5), fill=GREEN if lvl > 0.4 else RED)
    elif name == "clock":
        d.ellipse((cx - s, cy - s, cx + s, cy + s), fill=WHITE, outline=STEEL, width=8)
        a = t * 3; d.line([(cx, cy), (cx + s * 0.7 * math.cos(a), cy + s * 0.7 * math.sin(a))], fill=(30, 30, 30), width=10)
        d.line([(cx, cy), (cx, cy - s * 0.5)], fill=(30, 30, 30), width=12)
    elif name == "speed": gauge(d, cx, cy, s, 0.5 + 0.4 * math.sin(t * 2))
    elif name == "motor":
        wheel(d, cx - s * 0.9, cy + s * 0.3, s * 0.55, t * 4); wheel(d, cx + s * 0.9, cy + s * 0.3, s * 0.55, t * 4)
        d.polygon([(cx - s * 0.9, cy + s * 0.3), (cx - s * 0.2, cy - s * 0.35), (cx + s * 0.5, cy - s * 0.35), (cx + s * 0.9, cy + s * 0.3)], outline=(220, 224, 232), width=int(s * 0.08))
        d.rounded_rectangle((cx - s * 0.35, cy - s * 0.6, cx + s * 0.35, cy - s * 0.3), int(s * 0.12), fill=RED)
        d.line([(cx + s * 0.5, cy - s * 0.35), (cx + s * 0.75, cy - s * 0.8)], fill=(220, 224, 232), width=int(s * 0.07))
        d.ellipse((cx + s * 0.62, cy - s * 0.75, cx + s * 0.88, cy - s * 0.5), fill=YELLOW)

# ---------- subtitles ----------
def subtitle(d, seg, lt):
    words = seg["vo"].split(); chunks, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= 3 or w.endswith((".", ",", "?", ":", "!")): chunks.append(cur); cur = []
    if cur: chunks.append(cur)
    flat = [w for c in chunks for w in c]; tot = sum(len(w) + 1 for w in flat)
    speak = max(0.5, seg["dur"] - 0.35); acc = 0; wi = len(flat) - 1
    for i, w in enumerate(flat):
        acc += len(w) + 1
        if lt <= speak * acc / tot: wi = i; break
    idx = 0
    for c in chunks:
        if wi < idx + len(c): break
        idx += len(c)
    f = F(66); xt = sum(d.textlength(w + " ", font=f) for w in c)
    if xt > 1000: f = F(66 * 1000 / xt); xt = sum(d.textlength(w + " ", font=f) for w in c)
    x = W / 2 - xt / 2; y = 1560
    d.rounded_rectangle((x - 30, y - 58, x + xt + 14, y + 58), 30, fill=(0, 0, 0, 150))
    for j, w in enumerate(c):
        d.text((x, y), w, font=f, fill=YELLOW if (idx + j) == wi else WHITE, anchor="lm", stroke_width=6, stroke_fill=(0, 0, 0))
        x += d.textlength(w + " ", font=f)

# ---------- scenes ----------
# Tiap scene: fn(p, lt, bd, t, wimg, h) -> cam (z, cx, cy). lt = detik sejak beat mulai, bd = durasi beat.
def sc_hero(p, lt, bd, t, wimg, h):
    wimg.alpha_composite(HERO); wimg.alpha_composite(grad)
    if p.get("rain", True): rain(ImageDraw.Draw(wimg), t, 120)
    title(h, p.get("title"), lt, p.get("color", "white"), y=p.get("y", 300), size=p.get("size", 104), instant=p.get("instant", False))
    if p.get("pill"): pill(h, (W // 2, p.get("pill_y", 1320)), p["pill"], p.get("pill_color", "orange"), size=52, k=pop((lt - 0.4) / 0.3))
    f = lt / bd; z = p.get("zoom", [1.0, 1.12]); fc = p.get("focus", [0.5, 0.5])
    return (rng2(z, f), W * fc[0], H * fc[1])

def sc_hero_alert(p, lt, bd, t, wimg, h):
    wimg.alpha_composite(HERO); wimg.alpha_composite(grad)
    if p.get("rain", True): rain(ImageDraw.Draw(wimg), t, 120)
    v = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ImageDraw.Draw(v).rectangle((0, 0, W, H), outline=(235, 40, 30, 150), width=60)
    wimg.alpha_composite(v.filter(ImageFilter.GaussianBlur(40)))
    sh = int(12 * math.sin(t * 55)); kk = pop(lt / 0.25)
    txt = p.get("text", "AWAS!"); size = fit_size(h, [txt], p.get("size", 150))
    text_c(h, (W // 2 + sh, 330), txt, F(size * kk), fill=C(p.get("color", "red")), stroke=10)
    if kk > 0.6 and p.get("icon", "warn"): icon(h, p.get("icon", "warn"), W // 2, 560, 90, t)
    f = lt / bd; fc = p.get("focus", [0.5, 0.6]); z = p.get("zoom", [1.45, 1.65])
    return (rng2(z, f), W * fc[0], H * fc[1])

def sc_wheel(p, lt, bd, t, wimg, h):
    wd = ImageDraw.Draw(wimg); f = lt / bd
    wheel(wd, W // 2, 900, 430, t * 2.2)
    title(h, p.get("title"), lt, p.get("color", "orange"), y=260, size=96)
    if p.get("label") and f > 0.3: label(h, p["label"], (W // 2 + 30, 880), (W // 2 + 250, 1250), "blue", pop((lt - 0.3 * bd) / 0.3))
    return (1.0 + p.get("zoomin", 1.6) * ease(f), W / 2, 900)

def sc_drum(p, lt, bd, t, wimg, h):
    f = lt / bd; wd = ImageDraw.Draw(wimg)
    if p.get("rain"): rain(wd, t, 90)
    small = p.get("gauge") is not None
    cy, R = (760, 300) if small else (900, 430)
    drum(wimg, W // 2, cy, R, 0 if p.get("still") else t * 2.2, expand=rng2(p.get("expand", 0.6), ease(f)), heat=rng2(p.get("heat", 0), f),
         water=rng2(p.get("water", 0), ease(f)), mud=p.get("mud", 0), t=t, cracks=rng2(p.get("cracks", 0), ease(f)))
    title(h, p.get("title"), lt, p.get("color", "yellow"), y=p.get("y", 240), size=p.get("size", 86))
    if p.get("label"): label(h, p["label"], (W // 2 + 300, cy), (W // 2 + 260, 1420), "orange", pop((lt - 0.2 * bd) / 0.3))
    if p.get("arrows") and rng2(p.get("expand", 0.6), ease(f)) > 0.5:
        for s_ in (-1, 1): arrow(h, (W // 2 + s_ * 150, cy), (W // 2 + s_ * 300, cy), "yellow", 12)
    if small:
        g = p["gauge"]; gauge(h, W // 2, 1330, 230, lerp(g[0], g[1], ease(f / 0.6)), p.get("gauge_label"))
    if p.get("pill") and f > 0.5: pill(h, (W // 2, 380), p["pill"], p.get("pill_color", "red"), "white", 52, pop((f - 0.5) * bd / 0.3))
    z = p.get("zoom", [1.0, 1.08]); fc = p.get("focus", [0.5, cy / H])
    return (rng2(z, ease(f)), W * fc[0], H * fc[1])

def sc_plug(p, lt, bd, t, wimg, h):
    f = lt / bd; wd = ImageDraw.Draw(wimg)
    if p.get("rain"): rain(wd, t, 110)
    broken = p.get("broken", False); sh = int(10 * math.sin(t * 60)) if broken else 0
    plug(wd, W // 2 + 60 + sh, 960, 1.0, t, flow=p.get("flow", 1), crack=rng2(p.get("crack", 0), ease(f)), water=rng2(p.get("water", 0), f), spark=p.get("spark", 1), broken=broken)
    title(h, p.get("title"), lt, p.get("color", "orange"), y=240, size=88)
    for i, lb in enumerate(p.get("labels", [])):
        tips = {"cop": (W // 2 + 140, 860), "busi": (W // 2 + 100, 1080), "koil": (W // 2 - 220, 545)}
        ats = {"cop": (W // 2 + 330, 700), "busi": (W // 2 + 330, 1210), "koil": (W // 2 - 220, 420)}
        label(h, lb["text"], tips[lb["at"]], ats[lb["at"]], lb.get("color", "orange"), pop((lt - 0.3 - i * 0.6) / 0.3))
    if p.get("big"): text_c(h, (W // 2 + sh * 2, 1400), p["big"], F(110 * pop((lt - 0.4 * bd) / 0.3)), fill=C(p.get("big_color", "orange")), stroke=8)
    return (rng2(p.get("zoom", [1.0, 1.05]), f), W / 2, 960)

def sc_chain(p, lt, bd, t, wimg, h):
    f = lt / bd; wd = ImageDraw.Draw(wimg)
    if p.get("rain"): rain(wd, t, 90)
    chain(wd, W // 2, 960, 1.0, t * p.get("speed", 1.0), rust=rng2(p.get("rust", 0), ease(f)), oil=rng2(p.get("oil", 0), f), slack=rng2(p.get("slack", 0), ease(f)))
    title(h, p.get("title"), lt, p.get("color", "orange"), y=280, size=92)
    if p.get("pill"): pill(h, (W // 2, 1380), p["pill"], p.get("pill_color", "red"), "white", 52, pop((lt - 0.4) / 0.3))
    return (rng2(p.get("zoom", [1.0, 1.08]), f), W / 2, 960)

def sc_piston(p, lt, bd, t, wimg, h):
    wd = ImageDraw.Draw(wimg)
    piston(wd, W // 2, 880, 0.9, t, p.get("stage"))
    title(h, p.get("title"), lt, p.get("color", "orange"), y=230, size=86)
    return (1.0, W / 2, H / 2)

def sc_gauge(p, lt, bd, t, wimg, h):
    f = lt / bd; wd = ImageDraw.Draw(wimg)
    g = p.get("value", [0.2, 0.9]); gauge(wd, W // 2, 1000, 300, rng2(g, ease(f)) + 0.03 * math.sin(t * 4))
    if p.get("gauge_text"): text_c(wd, (W // 2, 1110), p["gauge_text"], F(70), fill=C(p.get("gauge_color", "green")), stroke=6)
    title(h, p.get("title"), lt, p.get("color", "white"), y=290, size=96)
    if p.get("icon"): icon(h, p["icon"], W // 2, 560, 70, t)
    return (1.0 + 0.08 * f, W / 2, 1000)

def sc_lever(p, lt, bd, t, wimg, h):
    k = lt / bd; wd = ImageDraw.Draw(wimg)
    n_ = p.get("presses", 3); cyc = (k * n_) % 1; press = math.sin(min(1, cyc / 0.5) * math.pi) if cyc < 0.5 else 0
    lever(wd, W // 2 + 60, 760, press)
    n = min(n_, int(k * n_) + 1); text_c(h, (W // 2, 560), p.get("count_text", "TEKAN PELAN") + f"  {n}x", F(74), fill=YELLOW, stroke=6)
    drum(wimg, W // 2 - 230, 1220, 170, t * 1.5, expand=0.8, water=max(0, 1 - k * 1.3), heat=0.3 * k)
    for i in range(5):
        ph = (t * 0.7 + i / 5) % 1; x = W // 2 - 230 + (i - 2) * 40; y = 1020 - ph * 160
        wd.ellipse((x - 18, y - 18, x + 18, y + 18), fill=(230, 235, 245, int(160 * (1 - ph))))
    gauge(h, W // 2 + 240, 1260, 150, lerp(0.15, 0.92, ease(k)))
    if k > 0.75: check(h, W // 2 + 240, 1060, 56); text_c(h, (W // 2 + 240, 1370), p.get("ok_text", "PAKEM"), F(44), fill=GREEN, stroke=4)
    title(h, p.get("title"), lt, p.get("color", "green"), y=300, size=96)
    return (1.0, W / 2, H / 2)

def sc_icons(p, lt, bd, t, wimg, h):
    f = lt / bd; wd = ImageDraw.Draw(wimg)
    if p.get("rain"): rain(wd, t, 90)
    for i, ic in enumerate(p.get("items", [])):
        k = ease((lt - i * 0.25) / 0.35)
        if k <= 0: continue
        icon(wd, ic["icon"], ic.get("x", 540), ic.get("y", 1000) + (1 - k) * 80, ic.get("size", 150), t)
        if ic.get("label"): text_c(wd, (ic.get("x", 540), ic.get("y", 1000) + ic.get("size", 150) + 60), ic["label"], F(46), fill=WHITE, stroke=4)
    title(h, p.get("title"), lt, p.get("color", "white"), y=p.get("y", 280), size=p.get("size", 92))
    if p.get("pill"): pill(h, (W // 2, p.get("pill_y", 330 if not p.get("title") else 520)), p["pill"], p.get("pill_color", "orange"), size=50, k=pop(lt / 0.25))
    if p.get("big"): text_c(h, (W // 2, p.get("big_y", 620)), p["big"], F(150 * pop(lt / 0.25)), fill=C(p.get("big_color", "yellow")), stroke=10)
    sh = p.get("shake", 0)
    return (1.0 + p.get("zoomin", 0.06) * f + sh * 0.04 * math.sin(t * 40), W / 2, p.get("focus_y", 1000))

def sc_checklist(p, lt, bd, t, wimg, h):
    title(h, p.get("title"), lt, p.get("color", "green"), y=220, size=100)
    items = p.get("items", []); y0 = p.get("y0", 480)
    for i, it in enumerate(items):
        k = ease((lt - 0.35 - i * min(0.9, (bd - 0.6) / max(1, len(items)))) / 0.4)
        if k <= 0: continue
        x = 90 + (1 - k) * 200; y = y0 + i * 190
        h.rounded_rectangle((x, y, x + 900, y + 150), 34, fill=(255, 255, 255, int(235 * k)))
        mk = it.get("mark", str(i + 1)); col = C(it.get("color", ["orange", "red", "green", "blue"][i % 4]))
        if mk == "v": check(h, x + 75, y + 75, 45, col)
        elif mk == "x": cross(h, x + 75, y + 75, 45, col)
        else: h.ellipse((x + 30, y + 30, x + 120, y + 120), fill=col); text_c(h, (x + 75, y + 75), mk, F(56), fill=WHITE)
        lines = it["text"].split("\n")
        for j, ln in enumerate(lines):
            h.text((x + 150, y + 75 + (j - (len(lines) - 1) / 2) * 52), ln, font=F(fit_size(h, [ln], 44, 720)), fill=(20, 24, 34), anchor="lm")
    return (1.0, W / 2, H / 2)

def sc_mythfact(p, lt, bd, t, wimg, h):
    f = lt / bd
    pill(h, (W // 2, 330), "MITOS", "red", "white", 70, pop(lt / 0.3))
    for j, ln in enumerate(p.get("myth", "").split("\n")): text_c(h, (W // 2, 480 + j * 80), ln, F(64), fill=WHITE, stroke=6)
    if f > 0.45:
        k = pop((f - 0.45) * bd / 0.3)
        h.line([(140, 470), (940, 560)], fill=RED, width=14) if k > 0.5 else None
        pill(h, (W // 2, 820), "FAKTA", "green", "white", 70, k)
        for j, ln in enumerate(p.get("fact", "").split("\n")): text_c(h, (W // 2, 980 + j * 80), ln, F(62 * min(1, k)), fill=YELLOW, stroke=6)
        if k > 0.6: check(h, W // 2, 1290, 70)
    return (1.0, W / 2, H / 2)

def sc_bigtext(p, lt, bd, t, wimg, h):
    wd = ImageDraw.Draw(wimg)
    if p.get("rain"): rain(wd, t, 90)
    sh = int(10 * math.sin(t * 50)) if p.get("shake") else 0
    size = fit_size(h, [p.get("text", "")], p.get("size", 150))
    text_c(h, (W // 2 + sh, 820), p.get("text", ""), F(size * pop(lt / 0.3)), fill=C(p.get("color", "yellow")), stroke=10)
    if p.get("sub"): text_c(h, (W // 2, 1000), p["sub"], F(fit_size(h, [p["sub"]], 58)), fill=WHITE, stroke=6)
    if p.get("icon"): icon(h, p["icon"], W // 2, 560, 90, t)
    return (1.0 + 0.05 * lt / bd, W / 2, H / 2)

def sc_cta(p, lt, bd, t, wimg, h):
    wimg.alpha_composite(HERO_BLUR); wimg.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, 140)))
    rain(ImageDraw.Draw(wimg), t, 80)
    if p.get("badge"): pill(h, (W // 2, 520), p["badge"], "blue", "white", 50, pop(lt / 0.3))
    title(h, p.get("title", ["SIMPAN &", "FOLLOW!"]), lt, "white", y=760, size=130, start=0.2)
    if lt > 0.8:
        k = pop((lt - 0.8) / 0.3) * (1 + 0.05 * math.sin(t * 8)); bw, bh = int(560 * k), int(140 * k)
        h.rounded_rectangle((W // 2 - bw // 2, 1080 - bh // 2, W // 2 + bw // 2, 1080 + bh // 2), 70, fill=ORANGE)
        if k > 0.6: text_c(h, (W // 2, 1080), "FOLLOW", F(76), fill=(15, 15, 20))
    if lt > 1.4 and p.get("next"): text_c(h, (W // 2, 1250), p["next"], F(fit_size(h, [p["next"]], 44)), fill=(220, 228, 240), stroke=3)
    if p.get("refs"): text_c(h, (W // 2, 1880), "Referensi: " + p["refs"], F(28, False), fill=(170, 180, 200))
    return (1.0, W / 2, H / 2)

SCENES = {"hero": sc_hero, "hero_alert": sc_hero_alert, "wheel": sc_wheel, "drum": sc_drum, "plug": sc_plug, "chain": sc_chain,
          "piston": sc_piston, "gauge": sc_gauge, "lever": sc_lever, "icons": sc_icons, "checklist": sc_checklist,
          "mythfact": sc_mythfact, "bigtext": sc_bigtext, "cta": sc_cta}

def apply_cam(img, z, cx, cy):
    if abs(z - 1) < 1e-3: return img
    cw, ch = W / z, H / z
    x0 = min(max(cx - cw / 2, 0), W - cw); y0 = min(max(cy - ch / 2, 0), H - ch)
    return img.transform((W, H), Image.AFFINE, (1 / z, 0, x0, 0, 1 / z, y0), resample=Image.BILINEAR)

def main():
    global HERO, HERO_BLUR
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    stills = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--stills=")), None)
    spec = json.load(open(args[0], encoding="utf-8")); OUT = args[1]
    AUDIO = args[2] if len(args) > 2 else None; SFX = args[3] if len(args) > 3 else None
    hp = os.path.join(os.path.dirname(os.path.abspath(args[0])), "hero.png")
    if os.path.exists(hp):
        im = Image.open(hp).convert("RGB"); sc = max(W / im.width, H / im.height)
        im = im.resize((int(im.width * sc) + 1, int(im.height * sc) + 1), Image.LANCZOS)
        HERO = im.crop(((im.width - W) // 2, (im.height - H) // 2, (im.width - W) // 2 + W, (im.height - H) // 2 + H)).convert("RGBA")
    else:
        HERO = bg.copy(); hd = ImageDraw.Draw(HERO); icon(hd, "motor", W // 2, 1050, 300, 0.0)
    HERO_BLUR = HERO.filter(ImageFilter.GaussianBlur(18))
    segs = spec["segments"]; starts = []; t0 = 0
    for s in segs: starts.append(t0); t0 += s["dur"]
    TOTAL = t0; NF = int(math.ceil(TOTAL * FPS))

    def frame(i):
        t = i / FPS
        si = max(k for k in range(len(segs)) if starts[k] <= t + 1e-9)
        seg = segs[si]; lt = t - starts[si]; dur = seg["dur"]
        beats = seg["beats"]; bi = max(k for k in range(len(beats)) if beats[k].get("at", 0) * dur <= lt + 1e-9)
        b = beats[bi]; b0 = b.get("at", 0) * dur; b1 = beats[bi + 1]["at"] * dur if bi + 1 < len(beats) else dur
        blt, bdur = lt - b0, max(0.3, b1 - b0)
        wimg = bg.copy(); hud = Image.new("RGBA", (W, H), (0, 0, 0, 0)); h = ImageDraw.Draw(hud)
        if i == 0 and spec.get("thumb_title"):  # frame pertama = thumbnail
            wimg.alpha_composite(HERO); wimg.alpha_composite(grad)
            title(h, spec["thumb_title"], 1, "yellow", y=330, size=120, instant=True)
            z, cx, cy = 1.0, W / 2, H / 2
        else:
            z, cx, cy = SCENES[b["scene"]](b, blt, bdur, t, wimg, h)
        z *= 1 + 0.10 * (1 - ease(blt / 0.3))
        out = apply_cam(wimg, z, cx, cy)
        if blt < 0.14 and t > 0.2: out.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(150 * (1 - blt / 0.14)))))
        h.text((W - 50, 90), spec.get("tag", "#TipsMotor"), font=F(38), fill=(255, 255, 255, 190), anchor="rm")
        h.rounded_rectangle((60, 1820, W - 60, 1834), 7, fill=(255, 255, 255, 60))
        h.rounded_rectangle((60, 1820, 60 + (W - 120) * t / TOTAL, 1834), 7, fill=ORANGE)
        if i > 0: subtitle(h, seg, lt)
        out.alpha_composite(hud)
        return out.convert("RGB")

    if stills:
        for tt in [float(x) for x in stills.split(",")]:
            frame(min(NF - 1, int(tt * FPS))).resize((360, 640)).save(f"{OUT}_still_{tt:05.1f}.png")
        return
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-"]
    if AUDIO and SFX:
        cmd += ["-i", AUDIO, "-i", SFX, "-filter_complex", "[2:a]volume=0.55[s];[1:a][s]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.9[a]", "-map", "0:v", "-map", "[a]", "-c:a", "aac", "-b:a", "160k"]
    elif AUDIO:
        cmd += ["-i", AUDIO, "-c:a", "aac", "-b:a", "160k"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-shortest", OUT]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(NF): p.stdin.write(frame(i).tobytes())
    p.stdin.close(); p.wait()
    if p.returncode: raise SystemExit("ffmpeg gagal")
    print("render ok", OUT, round(TOTAL, 2))

if __name__ == "__main__":
    main()
