"""MEE animated reel renderer: script.json -> one 1080x1920 mp4 (no talking head, pure motion graphics).

  python mee_reel.py script.json

Look follows the MEE Fanpage design guideline: 135deg blue gradient #48BEEE->#1A8FD1, faint white checker
fading toward the text side, Dela Gothic One for titles/highlights, Be Vietnam Pro for body text, ONE
yellow->orange highlight per scene, white cards with navy #0E2A3D text, navy cards with white text.
The real MEE logo (logo_white.png) sits top-center on every frame inside the Reels safe zone and grows big
on the CTA end card. No red/purple/black. Text stays inside x 80..1000, y 250..1600 (Reels UI safe zone).

script.json:
{
  "output": "reel.mp4", "logo": "assets/logo_white.png", "music": true,
  "scenes": [ {"type": "hook"|"wrong"|"options"|"compare"|"quiz"|"cta", "dur": seconds, ...}, ... ]
}
Scene fields are documented on each build_* function below.
"""
import json, sys, os, math, subprocess, tempfile
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.environ.get("REEL_FONTS", os.path.expanduser("~/.reel-fonts"))
DELA = os.path.join(FONT_DIR, "DelaGothicOne-Regular.ttf")
def BVP(w): return os.path.join(FONT_DIR, f"BeVietnamPro-{w}.ttf")

W, H, FPS = 1080, 1920, 30
G1, G2 = (0x48, 0xBE, 0xEE), (0x1A, 0x8F, 0xD1)
BLUE, NAVY, WHITE, SKY = (0x2C, 0xAB, 0xE2), (0x0E, 0x2A, 0x3D), (255, 255, 255), (0x58, 0xBF, 0xE8)
H1, H2 = (0xFF, 0xE0, 0x4F), (0xFF, 0xA3, 0x4F)
WIPE = 0.4
SAFE_X = 80
_fc = {}


def font(path, size):
    k = (path, int(size))
    if k not in _fc: _fc[k] = ImageFont.truetype(path, int(size))
    return _fc[k]


# ------------------------------------------------------------------ drawing helpers
def gradient(w, h, c1=G1, c2=G2):
    x = np.linspace(0, 1, w)[None, :]; y = np.linspace(0, 1, h)[:, None]; t = (x * w + y * h) / (w + h)
    return Image.fromarray(np.stack([c1[i] + (c2[i] - c1[i]) * t for i in range(3)], -1).astype(np.uint8)).convert("RGBA")


def checker(w, h, cell=64, opacity=0.10):
    yy, xx = np.mgrid[0:h, 0:w]
    on = ((xx // cell + yy // cell) % 2 == 0).astype(np.float32)
    a = (on * np.clip((xx / w - 0.45) / 0.4, 0, 1) * opacity * 255).astype(np.uint8)
    im = Image.new("RGBA", (w, h), WHITE + (0,)); im.putalpha(Image.fromarray(a)); return im


def rmask(w, h, r):
    m = Image.new("L", (w, h), 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, w - 1, h - 1), r, fill=255); return m


def fit(txt, path, size, maxw, minsize=24):
    while size > minsize and font(path, size).getlength(txt) > maxw: size -= 2
    return size


def text_img(txt, size, path, fill, maxw=None):
    if maxw: size = fit(txt, path, size, maxw)
    f = font(path, size); w = int(f.getlength(txt)) + 12; h = int(size * 1.7)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); ImageDraw.Draw(im).text((4, int(size * .3)), txt, font=f, fill=fill)
    bb = im.getbbox(); return im.crop((0, bb[1] - 2, w, bb[3] + 2)) if bb else im


def hl_text(txt, size, maxw=None, path=DELA):
    if maxw: size = fit(txt, path, size, maxw)
    f = font(path, size); w = int(f.getlength(txt)) + 12; h = int(size * 1.7)
    m = Image.new("L", (w, h), 0); ImageDraw.Draw(m).text((4, int(size * .3)), txt, font=f, fill=255)
    g = gradient(w, h, H1, H2); g.putalpha(m); bb = g.getbbox(); return g.crop((0, bb[1] - 2, w, bb[3] + 2))


def wrap(txt, path, size, maxw):
    words, lines, cur = txt.split(), [], ""
    for w_ in words:
        t = (cur + " " + w_).strip()
        if font(path, size).getlength(t) <= maxw or not cur: cur = t
        else: lines.append(cur); cur = w_
    if cur: lines.append(cur)
    return lines


def para(txt, size, path, fill, maxw, gap=1.28):
    lines = wrap(txt, path, size, maxw)
    imgs = [text_img(l, size, path, fill) for l in lines]
    lh = int(size * gap); h = lh * (len(imgs) - 1) + max(i.height for i in imgs); w = max(i.width for i in imgs)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for k, li in enumerate(imgs): im.alpha_composite(li, ((w - li.width) // 2, k * lh))
    return im


def shadow(im, blur=16, alpha=70, off=10):
    a = im.getchannel("A").point(lambda v: v * alpha // 255)
    sh = Image.new("RGBA", (im.width + 80, im.height + 80), (0, 0, 0, 0))
    blk = Image.new("RGBA", im.size, (0, 30, 60, 255)); blk.putalpha(a); sh.alpha_composite(blk, (40, 40 + off))
    sh = sh.filter(ImageFilter.GaussianBlur(blur)); sh.alpha_composite(im, (40, 40)); return sh


def card(w, h, r=36, fill=WHITE, grad=False):
    c = gradient(w, h, H1, H2) if grad else Image.new("RGBA", (w, h), fill + (255,))
    c.putalpha(rmask(w, h, r)); return shadow(c)


def on_card(base_card, content, dx=0, dy=0):
    im = base_card.copy(); im.alpha_composite(content, ((im.width - content.width) // 2 + dx, (im.height - content.height) // 2 + dy - 5))
    return im


def check_badge(d=96):
    S = d * 4; im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    g = gradient(S, S, H1, H2); m = Image.new("L", (S, S), 0); ImageDraw.Draw(m).ellipse((0, 0, S - 1, S - 1), fill=255); g.putalpha(m)
    im.alpha_composite(g); ImageDraw.Draw(im).line([(S*.27, S*.52), (S*.44, S*.69), (S*.75, S*.34)], fill=NAVY, width=int(S*.11), joint="curve")
    return im.resize((d, d), Image.LANCZOS)


def cross_badge(d=96):
    S = d * 4; im = Image.new("RGBA", (S, S), (0, 0, 0, 0)); dr = ImageDraw.Draw(im)
    dr.ellipse((0, 0, S - 1, S - 1), fill=NAVY + (255,)); k = S * .3
    dr.line([(k, k), (S - k, S - k)], fill=WHITE, width=int(S * .1)); dr.line([(S - k, k), (k, S - k)], fill=WHITE, width=int(S * .1))
    return im.resize((d, d), Image.LANCZOS)


def starburst(r, rays=16):
    S = 2 * r + 4; m = Image.new("L", (S, S), 0)
    pts = [(S / 2 + (r if i % 2 == 0 else r * .62) * math.cos(math.pi * i / rays),
            S / 2 + (r if i % 2 == 0 else r * .62) * math.sin(math.pi * i / rays)) for i in range(rays * 2)]
    ImageDraw.Draw(m).polygon(pts, fill=255); g = gradient(S, S, H1, H2); g.putalpha(m); return g


def pill(txt, size, fg, bg, padx=46, pady=22, path=None, grad=False):
    t = text_img(txt, size, path or BVP("Black"), fg)
    w, h = t.width + 2 * padx, t.height + 2 * pady
    c = gradient(w, h, H1, H2) if grad else Image.new("RGBA", (w, h), bg + (255,))
    c.putalpha(rmask(w, h, h // 2)); c.alpha_composite(t, (padx, pady)); return shadow(c, 12, 60, 8)


def headline(title, hl, size=88, maxw=920):
    """White title + yellow->orange highlight; one line if it fits, else stacked."""
    a = text_img(title, size, DELA, WHITE) if title else None; b = hl_text(hl, size) if hl else None
    gap = int(size * .3) if (a and b) else 0
    if (a.width if a else 0) + gap + (b.width if b else 0) <= maxw:   # same baseline for both parts
        f = font(DELA, size); wa = int(f.getlength(title)) if title else 0; wb = int(f.getlength(hl)) if hl else 0
        w = wa + gap + wb + 16; h = int(size * 1.8); y0 = int(size * .35)
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        if title: ImageDraw.Draw(im).text((4, y0), title, font=f, fill=WHITE)
        if hl:
            m = Image.new("L", (w, h), 0); ImageDraw.Draw(m).text((4 + wa + gap, y0), hl, font=f, fill=255)
            g = gradient(w, h, H1, H2); g.putalpha(m); im.alpha_composite(g)
        return im.crop(im.getbbox())
    a = text_img(title, size, DELA, WHITE, maxw) if title else None; b = hl_text(hl, size, maxw) if hl else None
    parts = [x for x in (a, b) if x]; g = int(size * .25)
    w = max(x.width for x in parts); h = sum(x.height for x in parts) + g * (len(parts) - 1)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); y = 0
    for x in parts: im.alpha_composite(x, ((w - x.width) // 2, y)); y += x.height + g
    return im


def load_png(path, width):
    im = Image.open(path).convert("RGBA"); r = width / im.width
    return im.resize((int(im.width * r), int(im.height * r)), Image.LANCZOS)


# ------------------------------------------------------------------ item model
class Item:
    """An image placed with its centre at (cx, cy), appearing at t0 (scene-local seconds) with an animation."""
    def __init__(self, img, cx, cy, t0=0.0, anim="pop", sfx="pop", t_out=None, swaps=None, pulse=False, progress=None):
        self.img, self.cx, self.cy, self.t0, self.anim, self.sfx = img, cx, cy, t0, anim, sfx
        self.t_out, self.swaps, self.pulse, self.progress = t_out, swaps or [], pulse, progress

    def frame_img(self, t):
        img = self.img
        for ts, im in self.swaps:
            if t >= ts: img = im
        return img


def ease(x): return 1 - (1 - x) ** 3
def back(x, s=1.7): x -= 1; return 1 + (s + 1) * x ** 3 + s * x ** 2


def draw_item(out, it, t):
    if t < it.t0: return
    if it.t_out is not None and t >= it.t_out + 0.25: return
    img = it.frame_img(t); a = min(1, (t - it.t0) / 0.35); s = 1.0; dy = 0; alpha = 1.0
    if it.anim == "pop" and a < 1: s = 0.55 + 0.45 * back(a); alpha = min(1, a * 2.5)
    elif it.anim == "slide" and a < 1: dy = int(90 * (1 - ease(a))); alpha = ease(a)
    elif it.anim == "fade" and a < 1: alpha = a
    if it.pulse and a >= 1: s = 1 + 0.035 * math.sin((t - it.t0) * 2 * math.pi * 1.4)
    if it.t_out is not None and t >= it.t_out: alpha *= max(0, 1 - (t - it.t_out) / 0.25)
    if it.progress:  # reveal left->right (e.g. a strike line being drawn)
        p0, p1 = it.progress; p = ease(min(1, max(0, (t - p0) / (p1 - p0))))
        if p <= 0: return
        img = img.crop((0, 0, max(1, int(img.width * p)), img.height))
        x = int(it.cx - it.img.width / 2); out.alpha_composite(img, (x, int(it.cy - img.height / 2))); return
    if s != 1.0: img = img.resize((max(1, int(img.width * s)), max(1, int(img.height * s))), Image.BILINEAR)
    if alpha < 1: img = img.copy(); img.putalpha(img.getchannel("A").point(lambda v: int(v * alpha)))
    out.alpha_composite(img, (int(it.cx - img.width / 2), int(it.cy - img.height / 2 + dy)))


# ------------------------------------------------------------------ scene builders (all coordinates for 1080x1920)
def quote_card(txt, w=880, h=210, size=84):
    t = text_img(txt, size, BVP("ExtraBold"), NAVY, maxw=w - 100); return on_card(card(w, h), t), t


def build_hook(sc):
    """{"kicker": small line, "title": big Dela line, "quote": the sentence on a white card, "character": png path}"""
    it = []
    hd = headline(sc.get("title", ""), sc.get("highlight", ""), 92); top = 440
    if sc.get("kicker"):
        kt = text_img(sc["kicker"], 56, BVP("Bold"), WHITE, 900); it.append(Item(kt, 540, top + kt.height / 2, 0.05, "slide", None)); top += kt.height + 28
    it.append(Item(hd, 540, top + hd.height / 2, 0.2, "pop", None)); top += hd.height + 40
    qc, _ = quote_card(sc["quote"]); it.append(Item(qc, 540, top + qc.height / 2 - 40, 0.6, "pop"))
    if sc.get("character"):
        ch = load_png(sc["character"], 540); it.append(Item(ch, 540, 1600 - ch.height / 2, 0.35, "slide", None))
    return it


def build_wrong(sc):
    """{"label": pill text, "quote", "strike": word to cross out, "note": why it is wrong, "sub": short extra line}"""
    it = []
    it.append(Item(pill(sc.get("label", "SAI RỒI"), 50, WHITE, NAVY), 540, 500, 0.1, "pop"))
    qc, qt = quote_card(sc["quote"]); cx, cy = 540, 790
    it.append(Item(qc, cx, cy, 0.0, "fade", None))
    if sc.get("strike"):
        size = 84; f = font(BVP("ExtraBold"), size)
        while size > 24 and f.getlength(sc["quote"]) > 780: size -= 2; f = font(BVP("ExtraBold"), size)
        pre = sc["quote"].split(sc["strike"])[0]
        x0 = cx - qt.width / 2 + 4 + f.getlength(pre); wlen = f.getlength(sc["strike"])
        line = Image.new("RGBA", (int(wlen + 24), 14), H2 + (255,)); line.putalpha(rmask(line.width, 14, 7))
        it.append(Item(line, x0 - 12 + line.width / 2, cy + 2, 0.5, "none", "pop", progress=(0.5, 0.9)))
    it.append(Item(cross_badge(110), 960, cy - 95, 0.95, "pop"))
    if sc.get("note"): it.append(Item(para(sc["note"], 60, BVP("ExtraBold"), WHITE, 900), 540, 1090, 1.3, "slide"))
    if sc.get("sub"): it.append(Item(hl_text(sc["sub"], 76, 900), 540, 1320, 1.9, "pop"))
    if sc.get("character"):
        ch = load_png(sc["character"], 420); it.append(Item(ch, 540, 1600 - ch.height / 2, 0.4, "slide", None))
    return it


def build_options(sc):
    """{"title", "highlight", "items": [2-4 correct sentences], "note": closing tip}"""
    it = [Item(headline(sc.get("title", ""), sc.get("highlight", ""), 84), 540, 500, 0.05, "pop", None)]
    n = len(sc["items"]); y0 = 720; step = 190
    for k, s in enumerate(sc["items"]):
        base = card(880, 160); t = text_img(s, 62, BVP("ExtraBold"), NAVY, maxw=660)
        im = base.copy(); im.alpha_composite(t, (40 + 150, (im.height - t.height) // 2 - 5))
        im.alpha_composite(check_badge(92), (40 + 40, (im.height - 92) // 2 - 5))
        it.append(Item(im, 540, y0 + k * step, 0.5 + k * 0.9, "slide"))
    if sc.get("note"): it.append(Item(para(sc["note"], 50, BVP("Bold"), WHITE, 900), 540, y0 + n * step + 60, 0.6 + n * 0.9, "fade", None))
    return it


def build_compare(sc):
    """{"title", "highlight", "left": {"head","sub","ex":[...]}, "right": {...}, "note"}"""
    it = [Item(headline(sc.get("title", ""), sc.get("highlight", ""), 84), 540, 500, 0.05, "pop", None)]
    for k, side in enumerate(("left", "right")):
        d = sc[side]; w, h = 430, 600
        c = Image.new("RGBA", (w, h), NAVY + (255,)); c.putalpha(rmask(w, h, 40)); dr = c
        y = 50; ht = text_img(d["head"], 70, DELA, WHITE, w - 60); dr.alpha_composite(ht, ((w - ht.width) // 2, y)); y = 150
        st = hl_text(d["sub"], 54, w - 60, BVP("Black")); dr.alpha_composite(st, ((w - st.width) // 2, y)); y = 270
        for ex in d.get("ex", []):
            chip = Image.new("RGBA", (w - 60, 104), WHITE + (255,)); chip.putalpha(rmask(w - 60, 104, 30))
            et = text_img(ex, 48, BVP("ExtraBold"), NAVY, w - 100); chip.alpha_composite(et, ((chip.width - et.width) // 2, (104 - et.height) // 2 - 3))
            dr.alpha_composite(chip, (30, y)); y += 128
        it.append(Item(shadow(c), 300 + k * 480, 980, 0.5 + k * 1.1, "slide"))
    if sc.get("note"): it.append(Item(para(sc["note"], 48, BVP("Bold"), WHITE, 920), 540, 1400, 2.9, "fade", None))
    return it


def build_quiz(sc):
    """{"title", "highlight", "q": question with ___, "options": [a, b], "answer": index, "reveal": sec, "character"}"""
    it = [Item(headline(sc.get("title", ""), sc.get("highlight", ""), 84), 540, 500, 0.05, "pop", None)]
    qc, _ = quote_card(sc["q"], 900, 200, 78); it.append(Item(qc, 540, 720, 0.3, "pop"))
    rv = sc.get("reveal", 3.0)
    for k, o in enumerate(sc["options"]):
        lab = "AB"[k] + ". " + o; w, h = 410, 150
        def opt(state):
            if state == "right":
                c = gradient(w, h, H1, H2); c.putalpha(rmask(w, h, 40)); fg = NAVY
            else:
                c = Image.new("RGBA", (w, h), WHITE + (255,)); c.putalpha(rmask(w, h, 40)); fg = NAVY
            t = text_img(lab, 60, BVP("ExtraBold"), fg, w - 80); c.alpha_composite(t, ((w - t.width) // 2, (h - t.height) // 2 - 4))
            if state == "wrong": c.putalpha(c.getchannel("A").point(lambda v: v * 40 // 100))
            return shadow(c)
        state = "right" if k == sc["answer"] else "wrong"
        it.append(Item(opt("idle"), 300 + k * 480, 960, 0.8 + k * 0.25, "pop", swaps=[(rv, opt(state))]))
        badge = check_badge(100) if state == "right" else cross_badge(90)
        it.append(Item(badge, 300 + k * 480 + 175, 880, rv, "pop", "ding" if state == "right" else None))
    if sc.get("character"):
        ch = load_png(sc["character"], 520); it.append(Item(ch, 540, 1600 - ch.height / 2, 0.5, "slide", None))
    return it


def build_cta(sc, logo_path):
    """{"line1", "highlight", "sub", "button"} - big logo + call to action; the small corner logo is hidden here."""
    it = [Item(load_png(logo_path, 560), 540, 700, 0.1, "pop", "pop")]
    it.append(Item(headline(sc.get("line1", ""), sc.get("highlight", ""), 82, 920), 540, 1060, 0.6, "pop"))
    if sc.get("sub"): it.append(Item(para(sc["sub"], 46, BVP("SemiBold"), WHITE, 900), 540, 1250, 1.0, "fade", None))
    if sc.get("button"): it.append(Item(pill(sc["button"], 54, NAVY, None, 70, 30, grad=True), 540, 1420, 1.4, "pop", pulse=True))
    return it


BUILD = {"hook": build_hook, "wrong": build_wrong, "options": build_options, "compare": build_compare, "quiz": build_quiz}


# ------------------------------------------------------------------ main
def main():
    spec = json.load(open(sys.argv[1], encoding="utf-8"))
    os.chdir(os.path.dirname(os.path.abspath(sys.argv[1])))
    logo_path = spec.get("logo", "assets/logo_white.png")
    small_logo = load_png(logo_path, 230)
    BG = gradient(W, H); BG.alpha_composite(checker(W, H, 64, .10))
    scenes, t = [], 0.0
    for sc in spec["scenes"]:
        items = build_cta(sc, logo_path) if sc["type"] == "cta" else BUILD[sc["type"]](sc)
        scenes.append({"t": t, "dur": sc["dur"], "items": items, "cta": sc["type"] == "cta"}); t += sc["dur"]
    DUR = t
    ev = {"impact": [0.0], "whoosh": [], "pop": [], "ding": []}
    for k, s in enumerate(scenes):
        if k: ev["whoosh"].append(s["t"] + WIPE / 2)
        for it in s["items"]:
            if it.sfx: ev[it.sfx].append(s["t"] + it.t0 + (0.02 if it.sfx == "pop" else 0))

    yy, xx = np.mgrid[0:H, 0:W]; DIAG = (xx / W + yy / H) / 2.0

    def scene_frame(s, tl):
        out = BG.copy()
        if not s["cta"]: out.alpha_composite(small_logo, ((W - small_logo.width) // 2, 255))
        for it in s["items"]: draw_item(out, it, tl)
        return out

    work = tempfile.mkdtemp(prefix="meereel_")
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                            "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p", os.path.join(work, "_v.mp4")], stdin=subprocess.PIPE)
    n = int(DUR * FPS)
    for f in range(n):
        t = f / FPS; k = max(i for i, s in enumerate(scenes) if s["t"] <= t + 1e-6); s = scenes[k]; tl = t - s["t"]
        cur = scene_frame(s, tl)
        if k and tl < WIPE:
            prev = scene_frame(scenes[k - 1], scenes[k - 1]["dur"])
            p = ease(tl / WIPE); m = np.clip((p * 1.15 - DIAG) / 0.06, 0, 1)[..., None]
            A = np.asarray(prev, np.float32); B = np.asarray(cur, np.float32)
            comp = A * (1 - m) + B * m; band = np.clip(1 - np.abs(m - .5) / .5, 0, 1) * .5
            cur = Image.fromarray((comp * (1 - band) + 255 * band).astype(np.uint8))
        enc.stdin.write(cur.convert("RGB").tobytes())
    enc.stdin.close(); enc.wait()

    json.dump(ev, open(os.path.join(work, "ev.json"), "w"))
    subprocess.run([sys.executable, os.path.join(HERE, "mee_reel_audio.py"), work, f"{DUR:.3f}", os.path.join(work, "ev.json")], check=True)
    mus = "[1:a]volume=%s[m];" % ("0.55" if spec.get("music", True) else "0")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(work, "_v.mp4"), "-i", os.path.join(work, "_music.wav"),
                    "-i", os.path.join(work, "_sfx.wav"), "-filter_complex",
                    mus + "[2:a]volume=0.9[s];[m][s]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.95[a]",
                    "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
                    "-movflags", "+faststart", spec["output"]], check=True)
    print(f"done: {spec['output']} ({DUR:.1f}s, {n} frames, {os.path.getsize(spec['output']) / 2**20:.1f} MB)")


if __name__ == "__main__":
    main()
