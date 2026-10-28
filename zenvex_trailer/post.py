"""Kurgu: çekim karelerini birleştirir, renk/ışık efektleri, yazılar, logo kartı, ses tasarımı → mp4.

python3 post.py [preview]
"""
import math
import os
import random
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = "/home/user/promo3d"
PREVIEW = "preview" in sys.argv
SRC = os.path.join(ROOT, "out", "preview" if PREVIEW else "frames")
OUTF = os.path.join(ROOT, "out", "final_preview" if PREVIEW else "final")
W, H = (960, 540) if PREVIEW else (1920, 1080)
FPS = 24
GAME = "/home/user/eaquel/zenvex_online/android/app/src/main"
FONT_D = GAME + "/res/font/display_bold.ttf"
FONT_B = GAME + "/res/font/outfit_bold.ttf"
FONT_R = GAME + "/res/font/outfit_regular.ttf"
SFX = GAME + "/assets/sfx/"

SHOTS = [("A", 36), ("B", 36), ("C", 84), ("D1", 36), ("D2", 54), ("E", 48), ("F", 66)]
START = {}
_t = 0
for n, L in SHOTS:
    START[n] = _t
    _t += L
TOTAL = _t
HITS_D2 = [11, 36]
TITLE = "Zenvex Online"
S = W / 1920


def g(shot, f):
    """çekim içi kare (1..) → küresel kare (0..)"""
    return START[shot] + f - 1


# --------------------------------------------------------------------------- görüntü
def font(path, px):
    return ImageFont.truetype(path, max(8, int(px * S)))


def grade(a, k):
    """a: float32 0..1. Gölgeler hafif camgöbeği, parlaklar turuncu; kontrast; doygunluk."""
    lum = a @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    sh = np.clip(1 - lum * 2.2, 0, 1)[..., None]
    hi = np.clip(lum * 1.6 - 0.6, 0, 1)[..., None]
    a = a + sh * np.array([-0.012, 0.004, 0.022], np.float32) + hi * np.array([0.03, 0.01, -0.03], np.float32)
    a = np.clip((a - 0.035) / 0.965, 0, 1)  # derin siyahlar
    a = a * a * (3 - 2 * a) * 0.45 + a * 0.55  # S eğrisi
    m = a.mean(axis=2, keepdims=True)
    a = m + (a - m) * 1.12
    return np.clip(a, 0, 1)


_vig = None


def vignette(a, amt=0.38):
    global _vig
    if _vig is None:
        y, x = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.sqrt(((x - W / 2) / (W / 2)) ** 2 + ((y - H / 2) / (H / 2)) ** 2)
        _vig = (1 - amt * np.clip((r - 0.45) / 0.95, 0, 1) ** 1.6)[..., None].astype(np.float32)
    return a * _vig


def grain(a, f, amt=0.022):
    rng = np.random.default_rng(f)
    n = rng.normal(0, amt, (H // 2, W // 2)).astype(np.float32)
    n = np.repeat(np.repeat(n, 2, 0), 2, 1)[:H, :W, None]
    return np.clip(a + n * (0.4 + 0.6 * (1 - a)), 0, 1)


def shake(img, f, strength):
    if strength <= 0:
        return img
    rng = random.Random(f * 31)
    dx = int(rng.uniform(-1, 1) * strength * S)
    dy = int(rng.uniform(-1, 1) * strength * S)
    z = 1 + strength * 0.0025
    w2, h2 = int(W * z), int(H * z)
    big = img.resize((w2, h2), Image.BICUBIC)
    x0 = (w2 - W) // 2 + dx
    y0 = (h2 - H) // 2 + dy
    return big.crop((x0, y0, x0 + W, y0 + H))


def chroma(img, px):
    """renk sapması: kırmızı ve mavi kanalları zıt yönlere kaydırır"""
    if px <= 0:
        return img
    r, gch, b = img.split()
    r = r.transform(img.size, Image.AFFINE, (1, 0, -px, 0, 1, 0))
    b = b.transform(img.size, Image.AFFINE, (1, 0, px, 0, 1, 0))
    return Image.merge("RGB", (r, gch, b))


def text_layer(lines, alpha=1.0, glow=(255, 60, 20), scale=1.0, glitch=0.0, seed=0, y_center=0.5):
    """lines: [(metin, yazı tipi, px, renk, aralık)] → ortalanmış RGBA katman (parlamalı)"""
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    blocks = []
    for txt, fp, px, col, track in lines:
        ft = font(fp, px * scale)
        widths = [d.textlength(ch, font=ft) for ch in txt]
        tw = sum(widths) + track * S * scale * (len(txt) - 1)
        asc, desc = ft.getmetrics()
        blocks.append((txt, ft, col, track * S * scale, widths, tw, asc + desc))
    total_h = sum(b[6] for b in blocks) + 12 * S * (len(blocks) - 1)
    y = H * y_center - total_h / 2
    for txt, ft, col, tr, widths, tw, lh in blocks:
        x = W / 2 - tw / 2
        for ch, cw in zip(txt, widths):
            d.text((x, y), ch, font=ft, fill=col + (255,))
            x += cw + tr
        y += lh + 12 * S
    if glitch > 0:
        rng = random.Random(seed)
        arr = np.array(lay)
        for _ in range(int(14 * glitch)):
            y0 = rng.randrange(0, H - 4)
            hgt = rng.randrange(2, int(30 * S) + 3)
            arr[y0 : y0 + hgt] = np.roll(arr[y0 : y0 + hgt], int(rng.uniform(-60, 60) * S * glitch), axis=1)
        lay = Image.fromarray(arr)
    a = lay.split()[3]
    gl = Image.new("RGBA", (W, H), glow + (0,))
    gl.putalpha(a.filter(ImageFilter.GaussianBlur(18 * S)).point(lambda v: min(255, int(v * 1.6))))
    out = Image.alpha_composite(gl, lay)
    if alpha < 1:
        out.putalpha(out.split()[3].point(lambda v: int(v * alpha)))
    return out


def over(img, lay, glitch_rgb=0):
    base = img.convert("RGBA")
    if glitch_rgb:
        r, gch, b, a = lay.split()
        rl = Image.merge("RGBA", (r, Image.new("L", lay.size), Image.new("L", lay.size), a)).transform(lay.size, Image.AFFINE, (1, 0, -glitch_rgb, 0, 1, 0))
        bl = Image.merge("RGBA", (Image.new("L", lay.size), gch, b, a)).transform(lay.size, Image.AFFINE, (1, 0, glitch_rgb, 0, 1, 0))
        base = Image.alpha_composite(base, rl)
        base = Image.alpha_composite(base, bl)
    else:
        base = Image.alpha_composite(base, lay)
    return base.convert("RGB")


def env(f, a, b, fade=4):
    """[a, b] aralığında 0→1→0 zarf"""
    if f < a or f > b:
        return 0.0
    return min(1.0, (f - a + 1) / fade, (b - f + 1) / fade)


def pill(img, text, y_center, alpha):
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    ft = font(FONT_B, 40)
    tw = d.textlength(text, font=ft)
    pw, ph = tw + 90 * S, 78 * S
    x0, y0 = W / 2 - pw / 2, H * y_center - ph / 2
    d.rounded_rectangle((x0, y0, x0 + pw, y0 + ph), radius=ph / 2, fill=(200, 24, 18, 235), outline=(255, 140, 90, 255), width=max(1, int(3 * S)))
    asc, desc = ft.getmetrics()
    d.text((W / 2 - tw / 2, y0 + ph / 2 - (asc + desc) / 2 + 2 * S), text, font=ft, fill=(255, 245, 235, 255))
    gl = Image.new("RGBA", (W, H), (255, 50, 20, 0))
    gl.putalpha(lay.split()[3].filter(ImageFilter.GaussianBlur(22 * S)))
    out = Image.alpha_composite(gl, lay)
    out.putalpha(out.split()[3].point(lambda v: int(v * alpha)))
    return out


def frame(gf):
    """küresel kare → son görüntü"""
    for n, L in SHOTS:
        if START[n] <= gf < START[n] + L:
            shot, lf = n, gf - START[n] + 1
            break
    p = os.path.join(SRC, shot, "%04d.png" % lf)
    if os.path.exists(p):
        img = Image.open(p).convert("RGB")
        if img.size != (W, H):
            up = img.size[0] < W
            img = img.resize((W, H), Image.LANCZOS)
            if up:
                img = img.filter(ImageFilter.UnsharpMask(radius=1.4, percent=55, threshold=2))
    else:
        img = Image.new("RGB", (W, H), (20, 0, 0))
        ImageDraw.Draw(img).text((20, 20), "%s %d (yok)" % (shot, lf), fill=(255, 255, 255))
    # sarsıntı / renk sapması
    sh = 0.0
    ca = 0.0
    if shot == "B" and lf >= 27:
        sh = 6 + (lf - 27) * 1.5
        ca = 2 + (lf - 27)
    if shot == "C" and lf <= 6:
        sh = 10 - lf * 1.6
    if shot == "D2":
        for hf in HITS_D2:
            if 0 <= lf - hf < 7:
                sh = max(sh, 16 * (1 - (lf - hf) / 7))
                ca = max(ca, 6 * (1 - (lf - hf) / 7))
    if shot == "F" and 12 <= lf < 20:
        sh = 9 * (1 - (lf - 12) / 8)
    img = shake(img, gf, sh)
    img = chroma(img, int(ca * S))
    a = np.asarray(img, np.float32) / 255
    a = grade(a, gf)
    a = vignette(a)
    # flaşlar
    white = 0.0
    if shot == "B" and lf >= 32:
        white = [0.25, 0.55, 0.85, 1.0, 1.0][min(lf - 32, 4)]
    if shot == "C" and lf <= 5:
        white = [0.9, 0.6, 0.35, 0.15, 0.05][lf - 1]
    if shot == "D2":
        for hf in HITS_D2:
            if lf - hf in (0, 1):
                white = max(white, 0.45 if lf == hf else 0.15)
    dark = 0.0
    if shot == "A" and lf <= 4:
        dark = 1 - lf / 5
    if shot == "D2" and lf >= 52:
        dark = (lf - 51) / 3 * 0.9
    if shot == "E" and lf <= 3:
        dark = 1 - lf / 4
    if shot == "F" and lf <= 3:
        white = max(white, [0.7, 0.4, 0.15][lf - 1])
    a = a * (1 - dark)
    a = a + (np.array([1.0, 0.96, 0.9], np.float32) - a) * white
    a = grain(a, gf)
    img = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))

    # ----- yazılar
    if shot == "C":
        e1 = env(lf, 9, 40, 5)
        if e1 > 0:
            sc = 1.06 - 0.06 * min(1, (lf - 9) / 20)
            img = over(img, text_layer([("ŞEHİR DÜŞTÜ.", FONT_D, 128, (245, 238, 230), 6)], e1, scale=sc, y_center=0.42))
        e2 = env(lf, 46, 84, 5)
        if e2 > 0:
            sc = 1.06 - 0.06 * min(1, (lf - 46) / 24)
            gl = 1.0 if lf < 49 else 0.0
            img = over(img, text_layer([("SEN AYAKTA KAL.", FONT_D, 128, (255, 92, 48), 6)], e2, scale=sc, glitch=gl, seed=lf, y_center=0.42), glitch_rgb=int(8 * S * gl))
    if shot == "E":
        if lf >= 8:
            gl = max(0.0, 1 - (lf - 8) / 7)
            e = env(lf, 8, 48, 3)
            img = over(img, text_layer([("EFSANEVİ SİLAH", FONT_B, 34, (255, 170, 140), 10), ("KAN AYI ORAĞI", FONT_D, 140, (255, 236, 228), 8)],
                                       e, glow=(255, 30, 20), glitch=gl, seed=lf, y_center=0.76), glitch_rgb=int(10 * S * gl))
    if shot == "F":
        if lf >= 12:
            k = min(1.0, (lf - 12) / 6)
            sc = 1.25 - 0.25 * (1 - (1 - k) ** 3)
            gl = 1.0 if lf < 15 else 0.0
            img = over(img, text_layer([(TITLE, FONT_D, 170, (255, 244, 236), 8)],
                                       k, glow=(255, 50, 18), scale=sc, glitch=gl, seed=lf, y_center=0.2), glitch_rgb=int(10 * S * gl))
        if lf >= 32:
            k = min(1.0, (lf - 32) / 5)
            pul = 1 + 0.03 * math.sin((lf - 32) / 24 * math.tau * 1.2) if lf > 37 else 1
            img = img.convert("RGBA")
            img = Image.alpha_composite(img, pill(img, "Şimdi Ücretsiz Oyna", 0.855, k)).convert("RGB")
            if lf >= 38:
                k2 = min(1.0, (lf - 38) / 5)
                img = over(img, text_layer([("Beta Açıldı!", FONT_D, 64, (255, 236, 214), 4)], k2, glow=(255, 70, 20), y_center=0.935))
    return img


def render_video():
    os.makedirs(OUTF, exist_ok=True)
    for gf in range(TOTAL):
        frame(gf).save(os.path.join(OUTF, "%04d.png" % gf), compress_level=1)
        if gf % 24 == 0:
            print("kurgu", gf, "/", TOTAL, flush=True)


# --------------------------------------------------------------------------- ses
SR = 48000


def load(name, gain=1.0):
    p = SFX + name
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"], capture_output=True, check=True)
    return np.frombuffer(r.stdout, np.float32).reshape(-1, 2) * gain


def pitch(x, p):
    n = int(len(x) / p)
    idx = np.linspace(0, len(x) - 1, n)
    return np.stack([np.interp(idx, np.arange(len(x)), x[:, c]) for c in range(2)], 1).astype(np.float32)


def env_exp(n, attack, decay):
    t = np.arange(n) / SR
    return (np.minimum(1, t / max(attack, 1e-4)) * np.exp(-t / decay)).astype(np.float32)


def boom(dur=2.2, f0=70, f1=28, gain=1.0, noise=0.35, seed=1):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = f1 + (f0 - f1) * np.exp(-t * 3.0)
    ph = 2 * np.pi * np.cumsum(f) / SR
    s = np.sin(ph) * env_exp(n, 0.004, 0.65)
    rng = np.random.default_rng(seed)
    nz = rng.normal(0, 1, n).astype(np.float32)
    k = int(SR / 900)
    nz = np.convolve(nz, np.ones(k) / k, "same") * env_exp(n, 0.002, 0.18) * noise * 3
    x = (s + nz) * gain
    x = np.tanh(x * 1.4) / 1.1
    return np.stack([x, x], 1).astype(np.float32)


def whoosh(dur=0.5, gain=0.5, seed=3, rise=True):
    n = int(dur * SR)
    rng = np.random.default_rng(seed)
    nz = rng.normal(0, 1, n).astype(np.float32)
    t = np.arange(n) / n
    e = (np.sin(np.pi * t ** (0.7 if rise else 1.4)) ** 2).astype(np.float32)
    # kayan bant: hareketli ortalama genişliği zamanla değişir
    out = np.zeros(n, np.float32)
    for k, w in ((4, 0.5), (10, 0.35), (24, 0.25)):
        out += np.convolve(nz, np.ones(k) / k, "same") * w
    x = out * e * gain
    pan = np.sin(np.pi * t) * 0.6
    return np.stack([x * (1 - pan * 0.5), x * (0.5 + pan * 0.5)], 1).astype(np.float32)


def riser(dur=3.4, gain=0.35):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 110 * (2 ** (t / dur * 2.5))
    ph = 2 * np.pi * np.cumsum(f) / SR
    s = (np.sin(ph) + 0.5 * np.sin(ph * 1.5) + 0.3 * np.sin(ph * 2.01)) / 1.8
    rng = np.random.default_rng(9)
    nz = rng.normal(0, 1, n).astype(np.float32) * 0.25
    e = (t / dur) ** 2.2
    x = (s + nz) * e * gain
    return np.stack([x, x], 1).astype(np.float32)


def drone(dur, gain=0.18):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = np.zeros(n)
    for fr, a in ((36.7, 1.0), (55.0, 0.6), (73.4, 0.35), (110.0, 0.15), (36.9, 0.8)):
        x += a * np.sin(2 * np.pi * fr * t + np.sin(t * 0.7) * 0.5)
    x *= (0.75 + 0.25 * np.sin(2 * np.pi * t * 0.25)) / 2.9
    return np.stack([x, x * 0.98], 1).astype(np.float32) * gain


def shing(dur=1.6, gain=0.35):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = np.zeros(n)
    for fr, a in ((2637, 1.0), (3951, 0.6), (5274, 0.4), (1318, 0.5)):
        x += a * np.sin(2 * np.pi * fr * t) * np.exp(-t * (2.5 + fr / 2000))
    x *= gain / 2.5
    return np.stack([x * 0.9, x], 1).astype(np.float32)


def taiko(gain=0.8, seed=2):
    return boom(0.7, 120, 55, gain, 0.6, seed)


def heartbeat(gain=0.6):
    a = boom(0.35, 60, 40, gain, 0.05, 5)
    b = boom(0.35, 55, 38, gain * 0.7, 0.05, 6)
    out = np.zeros((int(0.6 * SR), 2), np.float32)
    out[: len(a)] += a
    out[int(0.22 * SR) : int(0.22 * SR) + len(b)] += b
    return out


def audio(path):
    n = int(TOTAL / FPS * SR) + SR
    mix = np.zeros((n, 2), np.float32)

    def put(x, t, gain=1.0):
        i = int(t * SR)
        j = min(n, i + len(x))
        if j > i:
            mix[i:j] += x[: j - i] * gain

    T = lambda shot, f: g(shot, f) / FPS  # noqa: E731
    # altta sürekli karanlık drone (logo kartında yükselir)
    dr = drone(TOTAL / FPS + 0.5)
    fade = np.ones(len(dr), np.float32)
    fade[: int(0.4 * SR)] = np.linspace(0, 1, int(0.4 * SR))
    put(dr * fade[:, None], 0.0)
    # A: kor gözler yanar — derin vuruş + kalp atışı
    put(boom(2.5, 60, 26, 0.95, 0.25), T("A", 8))
    put(heartbeat(0.55), T("A", 22))
    put(whoosh(0.45, 0.25, 11), T("A", 30))
    # B: savuruş — vuuş, oyunun savuruş sesi, büyük çarpma
    put(whoosh(0.8, 0.6, 4), T("B", 6))
    put(pitch(load("swing.wav"), 0.72), T("B", 16), 0.9)
    put(pitch(load("swing.wav"), 0.6), T("B", 26), 0.8)
    put(riser(1.2, 0.25), T("B", 7))
    put(boom(3.0, 85, 24, 1.25, 0.7, 7), T("B", 34))
    put(pitch(load("explosion.wav"), 0.75), T("B", 34), 0.7)
    # C: gök gürültüsü, zombi inlemeleri, Titan kükremesi, gerilim yükselir
    put(load("thunder.wav"), T("C", 2), 0.55)
    for i, (f, nm) in enumerate([(14, "groan0.wav"), (26, "groan1.wav"), (40, "groan2.wav"), (58, "groan0.wav"), (70, "groan1.wav")]):
        put(pitch(load(nm), 0.85 + 0.1 * (i % 3)), T("C", f), 0.45)
    put(pitch(load("boss.wav"), 0.7), T("C", 50), 0.7)
    put(riser(3.4, 0.33), T("C", 4))
    put(taiko(0.7, 3), T("C", 46))
    # D1: koşu — adımlar ve davullar
    for k in range(9):
        put(load("step0.ogg" if k % 2 == 0 else "step1.ogg"), T("D1", 2 + k * 4), 0.6)
    for k in range(4):
        put(taiko(0.75, 10 + k), T("D1", 1 + k * 9))
    put(whoosh(0.6, 0.5, 21), T("D1", 26))
    # D2: kombo — savuruş + vuruş + zombi ölümü
    for hf in HITS_D2:
        put(pitch(load("swing.wav"), 0.8), T("D2", hf - 5), 0.85)
        put(load("hit.ogg"), T("D2", hf), 1.0)
        put(boom(1.2, 110, 40, 0.9, 0.8, hf), T("D2", hf))
        put(pitch(load("zdeath.wav"), 0.9), T("D2", hf + 1), 0.6)
    put(load("rage.wav"), T("D2", 20), 0.35)
    # E: silah — metalik parıltı + kalp atışı
    put(shing(2.0, 0.4), T("E", 4))
    put(boom(1.8, 70, 30, 0.7, 0.2, 31), T("E", 8))
    put(heartbeat(0.45), T("E", 24))
    # F: logo — büyük vuruş, gök gürültüsü
    put(boom(4.0, 90, 22, 1.35, 0.8, 41), T("F", 12))
    put(load("thunder.wav"), T("F", 13), 0.5)
    put(pitch(load("levelup.wav"), 0.85), T("F", 32), 0.35)
    # son: yumuşak sönme + sınırlama
    end = int(TOTAL / FPS * SR)
    mix = mix[: end + int(0.3 * SR)]
    tail = int(0.5 * SR)
    mix[-tail:] *= np.linspace(1, 0, tail)[:, None]
    peak = np.abs(mix).max()
    mix = np.tanh(mix / max(peak, 1e-6) * 1.6) * 0.89
    raw = path + ".f32"
    mix.astype(np.float32).tofile(raw)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", raw, "-c:a", "pcm_s16le", path], check=True)
    os.remove(raw)


def encode():
    wav = os.path.join(ROOT, "out", "audio.wav")
    audio(wav)
    mp4 = os.path.join(ROOT, "out", "zenvex_kael_preview.mp4" if PREVIEW else "zenvex_kael_trailer.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", os.path.join(OUTF, "%04d.png"), "-i", wav,
                    "-c:v", "libx264", "-preset", "slow", "-crf", "15" if not PREVIEW else "22", "-pix_fmt", "yuv420p", "-profile:v", "high",
                    "-c:a", "aac", "-b:a", "256k", "-shortest", "-movflags", "+faststart", mp4], check=True)
    print("VIDEO", mp4)


if __name__ == "__main__":
    if "audio" in sys.argv:
        audio(os.path.join(ROOT, "out", "audio.wav"))
    else:
        render_video()
        encode()
