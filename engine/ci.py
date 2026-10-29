"""hubozmt 渲染引擎(源自 Compositor 介绍片 v1):无限画布 + 节点 + 层级虚化/压暗。
纯 numpy / OpenCV / Pillow。世界坐标 = 缩放 1.0 时的屏幕像素。
画面尺寸由环境变量 HZ_SIZE 决定(如 1920x1080、1080x1920、1080x1080),必须在导入本模块前设置。"""
import os, math
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.environ.get("HZ_ASSETS", os.path.join(HERE, "assets")).rstrip(os.sep) + os.sep   # 本期素材目录
W, H = (int(v) for v in os.environ.get("HZ_SIZE", "1920x1080").lower().split("x"))
FPS = int(os.environ.get("CI_FPS", "60"))
SS = float(os.environ.get("CI_SS", "1.25"))            # 精灵超采样倍数
TAU = 2 * math.pi

# ------------------------------------------------------------------ 缓动
def clamp01(x): return min(1.0, max(0.0, x))
def lerp(a, b, t): return a + (b - a) * t
def smooth(x): x = clamp01(x); return x * x * (3 - 2 * x)

def cubic_bezier(x1, y1, x2, y2):
    def f(x):
        x = clamp01(x)
        lo, hi = 0.0, 1.0; t = x
        for _ in range(28):
            cx = 3 * x1 * t * (1 - t) ** 2 + 3 * x2 * t * t * (1 - t) + t ** 3
            if cx < x: lo = t
            else: hi = t
            t = (lo + hi) / 2
        return 3 * y1 * t * (1 - t) ** 2 + 3 * y2 * t * t * (1 - t) + t ** 3
    return f
E_OUT = cubic_bezier(0.22, 1, 0.36, 1)
E_EXPO = cubic_bezier(0.16, 1, 0.3, 1)
E_INOUT = cubic_bezier(0.76, 0, 0.24, 1)
E_SOFT = cubic_bezier(0.33, 1, 0.68, 1)
E_IN = cubic_bezier(0.55, 0.055, 0.675, 0.19)
E_LIN = lambda x: clamp01(x)
def e_back(x, c=1.7):
    x = clamp01(x); return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2

def hexc(h):  # '#rrggbb' -> (r,g,b) 0..1
    h = h.lstrip('#'); return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))

INK = hexc("#171513"); CREAM = hexc("#EFE9DD"); STONE = hexc("#9A9287"); DIMTX = hexc("#5E5850")
ORANGE = hexc("#FF8A3D"); ORANGE2 = hexc("#FFB36B"); TEAL = hexc("#34D1C4"); BLUE = hexc("#5B7CFF"); PINK = hexc("#FF5C8A")
GREEN = hexc("#4ADE80"); RED = hexc("#FF5C5C")

# ------------------------------------------------------------------ 精灵
class Sprite:
    """预乘 alpha float32 (h,w,4,RGBA)。锚点 = 中心。"""
    def __init__(self, img, ss=SS):
        self.img = np.ascontiguousarray(img, np.float32); self.ss = ss
        self.h, self.w = self.img.shape[:2]; self._mip = {0: self.img}; self._blur = {}
    @property
    def dw(self): return self.w / self.ss           # 设计宽
    @property
    def dh(self): return self.h / self.ss
    def mip(self, n):
        n = max(0, min(n, 5))
        if n not in self._mip:
            prev = self.mip(n - 1); self._mip[n] = cv2.resize(prev, (max(1, prev.shape[1] // 2), max(1, prev.shape[0] // 2)), interpolation=cv2.INTER_AREA)
        return self._mip[n]
    def blurred(self, sigma):
        key = int(round(sigma))
        if key <= 0: return self
        if key not in self._blur:
            self._blur[key] = Sprite(cv2.GaussianBlur(self.img, (0, 0), key), self.ss)
        return self._blur[key]

def pil_to_sprite(pil, ss=SS):
    a = np.asarray(pil.convert("RGBA"), np.float32) / 255.0
    a[..., :3] *= a[..., 3:4]
    return Sprite(a, ss)

def cv_to_rgba(bgr_or_bgra):
    im = bgr_or_bgra
    if im.shape[2] == 3: im = np.dstack([im, np.full(im.shape[:2], 255, np.uint8)])
    return Image.fromarray(cv2.cvtColor(im, cv2.COLOR_BGRA2RGBA))

# ------------------------------------------------------------------ 字体 / 文字
_FC = {}
def font(path, size):
    k = (path, int(size))
    if k not in _FC: _FC[k] = ImageFont.truetype(path, int(size))
    return _FC[k]
def is_cjk(ch): return ord(ch) >= 0x2E80
import sys as _sys
_sys.path.insert(1, os.path.join(HERE, "..", "library", "字体库"))
import fontlib as _fontlib
def _f(ch, size, weight, mono=False):
    """mono: False=sans 角色,True=mono 角色,字符串=字体库里的角色名(sans/serif/serif2/hand/punch/oblique/grot/bric/mono)。"""
    role = mono if isinstance(mono, str) else ("mono" if mono else "sans")
    return _fontlib.face(role, size, weight, ch=ch)

def advances(s, size, weight, tracking=0.0, mono=False):
    xs = []; x = 0.0
    for ch in s:
        xs.append(x); x += _f(ch, size, weight, mono).getlength(ch) + tracking * size
    return xs, x - tracking * size if s else 0.0

def _glyph_layer(s, size, weight, tracking, mono, pad, chars=None):
    """返回灰度 alpha(PIL L) 与度量;chars=[i] 只画指定字符。"""
    xs, tw = advances(s, size, weight, tracking, mono)
    asc = int(size * 1.0); box_h = int(size * 1.45)
    Wd = int(tw + 2 * pad); Hd = box_h + 2 * pad
    m = Image.new("L", (Wd, Hd), 0); d = ImageDraw.Draw(m)
    for i, ch in enumerate(s):
        if chars is not None and i not in chars: continue
        fo = _f(ch, size, weight, mono)
        d.text((pad + xs[i], pad + asc * 0.0), ch, font=fo, fill=255, anchor="la")
    return m, xs, tw, Wd, Hd

def _fill(m, color, grad=None):
    Wd, Hd = m.size; a = np.asarray(m, np.float32) / 255.0
    if grad is None:
        rgb = np.empty((Hd, Wd, 3), np.float32); rgb[:] = color
    else:  # grad = (c_top, c_bottom, y0_frac, y1_frac) 相对高度
        c0, c1, f0, f1 = grad; ys = np.clip((np.arange(Hd) / Hd - f0) / max(1e-6, (f1 - f0)), 0, 1)[:, None, None]
        rgb = np.array(c0, np.float32) * (1 - ys) + np.array(c1, np.float32) * ys; rgb = np.broadcast_to(rgb, (Hd, Wd, 3))
    return rgb, a

def text_sprite(s, size, weight=700, color=CREAM, grad=None, tracking=0.0, shadow=None, glow=None, mono=False, chars=None, alpha=1.0, pad=None, role=None):
    if role: mono = role
    """shadow=(dx,dy,blur,alpha);glow=(color,blur,alpha)。size=设计像素。"""
    S = size * SS; pad = int(pad if pad is not None else max(30, size * 0.35) * SS)
    m, xs, tw, Wd, Hd = _glyph_layer(s, S, weight, tracking, mono, pad, chars)
    rgb, a = _fill(m, color, grad); out = np.zeros((Hd, Wd, 4), np.float32)
    if shadow:
        dx, dy, bl, sa = shadow
        sh = cv2.GaussianBlur(np.asarray(m, np.float32) / 255.0, (0, 0), max(0.5, bl * SS))
        M = np.float32([[1, 0, dx * SS], [0, 1, dy * SS]]); sh = cv2.warpAffine(sh, M, (Wd, Hd)) * sa
        out[..., 3] = sh
    if glow:
        gc, gb, ga = glow; g = cv2.GaussianBlur(np.asarray(m, np.float32) / 255.0, (0, 0), gb * SS) * ga
        out[..., :3] += np.array(gc, np.float32) * g[..., None]; out[..., 3] = np.maximum(out[..., 3], g)
    a = a * alpha
    out[..., :3] = out[..., :3] * (1 - a[..., None]) + rgb * a[..., None]; out[..., 3] = out[..., 3] * (1 - a) + a
    sp = Sprite(out); sp.adv = [x / SS for x in xs]; sp.tw = tw / SS; sp.pad = pad / SS; return sp

def text_width(s, size, weight=700, tracking=0.0, mono=False): return advances(s, size, weight, tracking, mono)[1]

# ------------------------------------------------------------------ 形状 / 卡片
def rrect_mask(w, h, r, scale=4):
    m = Image.new("L", (int(w * scale), int(h * scale)), 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, w * scale - 1, h * scale - 1), r * scale, fill=255)
    return np.asarray(m.resize((int(w), int(h)), Image.LANCZOS), np.float32) / 255.0

def soft_shadow(alpha_mask, pad, blur, offset=(0, 0), opacity=0.5, spread=0):
    h, w = alpha_mask.shape; big = np.zeros((h + 2 * pad, w + 2 * pad), np.float32); big[pad:pad + h, pad:pad + w] = alpha_mask
    if spread: big = cv2.dilate(big, np.ones((spread * 2 + 1, spread * 2 + 1), np.uint8))
    big = cv2.GaussianBlur(big, (0, 0), blur) * opacity
    M = np.float32([[1, 0, offset[0]], [0, 1, offset[1]]]); return cv2.warpAffine(big, M, (w + 2 * pad, h + 2 * pad))

def card_from_rgb(rgb, w, radius=18, shadow=(50, 36, 22, 0.62), border=0.12, ss=SS, title=None, chrome=None):
    """rgb: HxWx3 float 0..1 或 uint8(RGB)。返回带阴影/描边的精灵。chrome='mac' 加窗口标题栏。"""
    if rgb.dtype == np.uint8: rgb = rgb.astype(np.float32) / 255.0
    ih, iw = rgb.shape[:2]; cw = int(w * ss); k = cw / iw; ch = int(ih * k)
    body = cv2.resize(rgb, (cw, ch), interpolation=cv2.INTER_AREA)
    bar = int(38 * ss) if chrome else 0
    full = np.zeros((ch + bar, cw, 3), np.float32); full[bar:] = body
    if chrome:
        full[:bar] = np.array(hexc("#2A2A2E"), np.float32)
        for i, c in enumerate(("#FF5F57", "#FEBC2E", "#28C840")):
            cv2.circle(full, (int((20 + i * 20) * ss), bar // 2), int(6 * ss), hexc(c), -1, cv2.LINE_AA)
        if title:
            pil = Image.fromarray((full[:bar] * 255).astype(np.uint8)); d = ImageDraw.Draw(pil)
            fo = _fontlib.face("sans", int(15 * ss), 500, ch=next((c for c in title if is_cjk(c)), "A")); d.text((cw / 2, bar / 2), title, font=fo, fill=(170, 168, 165), anchor="mm"); full[:bar] = np.asarray(pil, np.float32) / 255
    th = ch + bar; mask = rrect_mask(cw, th, radius * ss)
    pad = int((shadow[0] + shadow[2]) * ss) if shadow else int(6 * ss)
    out = np.zeros((th + 2 * pad, cw + 2 * pad, 4), np.float32)
    if shadow:
        sh = soft_shadow(mask, pad, shadow[2] * ss, (0, shadow[1] * ss * 0.5), shadow[3]); out[..., 3] = sh
    a = np.zeros_like(out[..., 3]); a[pad:pad + th, pad:pad + cw] = mask
    rgbp = np.zeros((th + 2 * pad, cw + 2 * pad, 3), np.float32); rgbp[pad:pad + th, pad:pad + cw] = full
    # 描边(内亮边)
    if border:
        er = cv2.erode(a, np.ones((3, 3), np.uint8)); rim = np.clip(a - er, 0, 1)[..., None]
        rgbp = rgbp * (1 - rim * border) + rim * border * 1.0
    out[..., :3] = out[..., :3] * (1 - a[..., None]) + rgbp * a[..., None]; out[..., 3] = out[..., 3] * (1 - a) + a
    sp = Sprite(out, ss); sp.pad = pad / ss; return sp

def flat_card(w, h, color, radius=20, shadow=(40, 28, 18, 0.5), border=0.10, alpha=1.0, gradient=None):
    ww, hh = int(w * SS), int(h * SS)
    if gradient:
        c0, c1 = gradient; t = np.linspace(0, 1, hh)[:, None, None]; rgb = np.array(c0, np.float32) * (1 - t) + np.array(c1, np.float32) * t; rgb = np.broadcast_to(rgb, (hh, ww, 3)).copy()
    else:
        rgb = np.empty((hh, ww, 3), np.float32); rgb[:] = color
    return card_from_rgb(rgb, w, radius, shadow, border)

def raster_sprite(draw_fn, w, h, ss=SS):
    """draw_fn(ImageDraw, scale) 在透明 RGBA 画布上作画,返回精灵(w,h 为设计尺寸)。"""
    im = Image.new("RGBA", (int(w * ss), int(h * ss)), (0, 0, 0, 0)); draw_fn(ImageDraw.Draw(im), ss, im); return pil_to_sprite(im, ss)

# ------------------------------------------------------------------ 元素 / 节点
class El:
    """sprite 放在节点局部坐标 (x,y);anim(t_local)->dict(a,dx,dy,s,rot,blur,reveal)。"""
    def __init__(self, spr, x=0, y=0, t0=0.0, anim=None, z=0.0, scale=1.0, rot=0.0, drift=(0, 0), t1=None, fade_out=0.3, custom=None, blend=None, name="", paint=None, ui=None):
        self.spr, self.x, self.y, self.t0, self.anim, self.z, self.scale, self.rot, self.drift, self.t1, self.fade_out, self.custom, self.blend, self.name, self.paint, self.ui = spr, x, y, t0, anim, z, scale, rot, drift, t1, fade_out, custom, blend, name, paint, ui
    def state(self, t):
        if t < self.t0: return None
        st = dict(a=1.0, dx=0.0, dy=0.0, s=1.0, sy=1.0, rot=0.0, blur=0.0, reveal=None, t=t, tl=t - self.t0)
        if self.anim: st.update(self.anim(t - self.t0))
        if self.custom: st.update(self.custom(t))
        if self.t1 is not None:
            if t >= self.t1 + self.fade_out: return None
            if t > self.t1: st["a"] *= 1 - smooth((t - self.t1) / max(1e-3, self.fade_out))
        dt = t - self.t0; st["dx"] += self.drift[0] * dt; st["dy"] += self.drift[1] * dt
        return st

# 动画构造器
def A_rise(d=0.8, dy=60, blur=0.0, ease=E_OUT, dx=0.0, s0=1.0):
    def f(t):
        p = ease(t / d); return dict(a=clamp01(t / (d * 0.55)) ** 1.2, dy=dy * (1 - p), dx=dx * (1 - p), blur=blur * (1 - clamp01(t / (d * 0.9))), s=lerp(s0, 1, p))
    return f
def A_pop(d=0.55, s0=0.78, c=1.6, blur=0.0):
    def f(t):
        p = clamp01(t / d); return dict(a=clamp01(t / (d * 0.35)), s=lerp(s0, 1, e_back(p, c)), blur=blur * (1 - E_OUT(p)))
    return f
def A_drop(d=0.75, dy=-300, rot0=-5.0, s0=1.12, ease=E_OUT):
    def f(t):
        p = ease(t / d); return dict(a=clamp01(t / (d * 0.4)), dy=dy * (1 - p), rot=rot0 * (1 - p), s=lerp(s0, 1, p), blur=(1 - p) * 6)
    return f
def A_wipe(d=0.8, ease=E_EXPO, soft=0.18):
    def f(t):
        return dict(a=1.0, reveal=(ease(t / d), soft))
    return f
def A_fade(d=0.4): return lambda t: dict(a=clamp01(t / d))

class Node:
    def __init__(self, name, t_in, pos, zoom=1.0, flight=0.7, ease=E_EXPO, drift=(0.0, 0.0, 0.0), lead=0.8, pre=0.75, toff=0.0, shift=0.0):
        """t_in:镜头到位时刻;flight:飞行时长;drift=(dzoom/s, dx/s, dy/s)。"""
        self.name, self.t_in, self.pos, self.zoom, self.flight, self.ease, self.drift, self.lead, self.pre = name, t_in + shift, np.array(pos, float), zoom, flight, ease, drift, lead, pre
        self.toff, self.shift = toff, shift
        self.els = []; self.bg_tint = None; self.keys = []; self.style = None
    def add(self, el):
        if el.ui is None: el.ui = True
        self.els.append(el); return el
    def key(self, t0, t1, off=(0, 0), zoom=1.0, ease=None):
        """节点内部运镜关键帧:相对节点中心的偏移 + 缩放倍数。"""
        self.keys.append((t0 + self.shift + self.toff, t1 + self.shift + self.toff, (off[0], off[1], zoom), ease or E_INOUT)); return self
    def view_at_rest(self, t):
        cur = np.array([0.0, 0.0, 1.0]); out = cur.copy()
        for (t0, t1, tg, ease) in self.keys:
            if t < t0: break
            tg = np.array(tg, float); f = ease(clamp01((t - t0) / max(1e-6, t1 - t0)))
            out = np.array([lerp(cur[0], tg[0], f), lerp(cur[1], tg[1], f), math.exp(lerp(math.log(cur[2]), math.log(tg[2]), f))])
            if t >= t1: cur = tg
            else: break
        dt = max(0.0, t - self.t_in)
        return (self.pos[0] + out[0] + self.drift[1] * dt, self.pos[1] + out[1] + self.drift[2] * dt, self.zoom * out[2] * (1 + self.drift[0] * dt))

def vw_interp(c0, w0, c1, w1, f, rho=1.4):
    c0 = np.asarray(c0, np.float64); c1 = np.asarray(c1, np.float64); d = c1 - c0; u1 = float(np.hypot(*d))
    if u1 < 1e-6: return c0, w0 * (w1 / w0) ** f
    b0 = (w1 ** 2 - w0 ** 2 + rho ** 4 * u1 ** 2) / (2 * w0 * rho ** 2 * u1)
    b1 = (w1 ** 2 - w0 ** 2 - rho ** 4 * u1 ** 2) / (2 * w1 * rho ** 2 * u1)
    r0 = math.log(-b0 + math.sqrt(b0 * b0 + 1)); r1 = math.log(-b1 + math.sqrt(b1 * b1 + 1)); S = (r1 - r0) / rho
    s = f * S
    u = w0 / rho ** 2 * math.cosh(r0) * math.tanh(rho * s + r0) - w0 / rho ** 2 * math.sinh(r0)
    w = w0 * math.cosh(r0) / math.cosh(rho * s + r0)
    return c0 + d / u1 * u, w

DEFAULT_STYLE = dict(base_c=(0.137, 0.133, 0.145), base_e=(0.043, 0.043, 0.047), gobo=0.04, dots=0.07, vign=0.38, grain=0.016, bloom=0.0, blobs=[])

class Scene:
    def __init__(self, nodes, duration, bg, old_fade=False, ramp=0.8):
        self.nodes = nodes; self.duration = duration; self.bg = bg; self.old_fade = old_fade; self.ramp = ramp
        self.nodes.sort(key=lambda n: n.t_in)
    def flight_state(self, t):
        """返回 (上一个节点, 当前节点, 飞行进度 0..1)。"""
        ns = self.nodes; cur = ns[0]; prev = None
        for i, n in enumerate(ns):
            if t >= n.t_in - n.flight * n.pre: cur, prev = n, (ns[i - 1] if i else None)
        if prev is None: return cur, cur, 1.0
        t_start = cur.t_in - cur.flight * cur.pre
        if t >= t_start + cur.flight: return cur, cur, 1.0
        return prev, cur, float(cur.ease((t - t_start) / cur.flight))
    def style(self, t):
        """背景风格:在节点之间随镜头飞行平滑过渡。无节点风格时返回 None(沿用旧背景)。"""
        if not any(n.style for n in self.nodes): return None
        a, b, f = self.flight_state(t); k = smooth(f); sa, sb = a.style or DEFAULT_STYLE, b.style or DEFAULT_STYLE
        mix = lambda x, y: tuple(lerp(p, q, k) for p, q in zip(x, y))
        st = dict(base_c=mix(sa["base_c"], sb["base_c"]), base_e=mix(sa["base_e"], sb["base_e"]))
        for key in ("gobo", "dots", "vign", "grain", "bloom"): st[key] = lerp(sa.get(key, 0.0), sb.get(key, 0.0), k)
        bl = []
        if a is b: bl = [(a.pos[0] + dx, a.pos[1] + dy, c, r, m) for (dx, dy, c, r, m) in sa.get("blobs", [])]
        else:
            bl += [(a.pos[0] + dx, a.pos[1] + dy, c, r, m * (1 - k)) for (dx, dy, c, r, m) in sa.get("blobs", [])]
            bl += [(b.pos[0] + dx, b.pos[1] + dy, c, r, m * k) for (dx, dy, c, r, m) in sb.get("blobs", [])]
        st["blobs"] = bl; return st
    def camera(self, t):
        ns = self.nodes
        cur = ns[0]; prev = None
        for i, n in enumerate(ns):
            t_start = n.t_in - n.flight * n.pre
            if t >= t_start: cur, prev = n, (ns[i - 1] if i else None)
        if prev is None: return cur.view_at_rest(t)
        t_start = cur.t_in - cur.flight * cur.pre; t_end = t_start + cur.flight
        if t >= t_end: return cur.view_at_rest(t)
        f = cur.ease((t - t_start) / cur.flight)
        a = prev.view_at_rest(t_start); b = cur.view_at_rest(t_end)
        # van Wijk 缩放平移;距离近时回落为线性
        c, w = vw_interp((a[0], a[1]), W / a[2], (b[0], b[1]), W / b[2], f, rho=1.25)
        return (float(c[0]), float(c[1]), W / w)
    def fades(self, t):
        """每个节点被下一个节点替代后的渐隐透明度(1=完全可见)。无后继者为 1。"""
        out = []
        for i, n in enumerate(self.nodes):
            if i + 1 >= len(self.nodes): out.append(1.0); continue
            m = self.nodes[i + 1]; st = m.t_in - m.flight * m.pre
            out.append(1.0 - smooth((t - st - 0.2) / 1.5))
        return out
    def levels(self, t):
        """每个节点的层级 L(0=焦点,1=上一层,2=更深);及可见性。"""
        out = []
        for i, n in enumerate(self.nodes):
            L = 0.0
            for m in self.nodes[i + 1:]:
                L += smooth((t - (m.t_in - m.flight * m.pre)) / self.ramp)
            out.append(L)
        return out

# ------------------------------------------------------------------ 绘制
def _over(dst, src):  # 预乘 over,dst/src: (h,w,4)
    dst *= (1 - src[..., 3:4]); dst += src

def draw_el(canvas, el, st, node_pos, cam, rs, push, dim_rgb=1.0):
    cx, cy, cz = cam; spr = el.spr
    kz = 1 + 0.045 * el.z
    if spr is None:      # 自绘元素:paint(canvas, f, k, st);f(局部x,y)->画布坐标,k=设计像素->画布像素
        if st["a"] <= 0.003: return
        kk0 = el.scale * st["s"] * cz * kz * push * rs
        f = lambda lx, ly: (((node_pos[0] + (el.x + st["dx"] + lx) * push - cx) * cz * kz + W / 2) * rs, ((node_pos[1] + (el.y + st["dy"] + ly) * push - cy) * cz * kz + H / 2) * rs)
        el.paint(canvas, f, kk0, st); return
    wx = node_pos[0] + (el.x + st["dx"]) * push; wy = node_pos[1] + (el.y + st["dy"]) * push
    sx = (wx - cx) * cz * kz + W / 2; sy = (wy - cy) * cz * kz + H / 2
    k = el.scale * st["s"] * cz * kz * push / spr.ss * rs          # 精灵像素 -> 画布像素
    if k < 1e-3 or st["a"] <= 0.003: return
    # 选 mip
    n = 0; kk = k
    while kk < 0.55 and n < 5: n += 1; kk *= 2
    sp = spr
    if st["blur"] > 0.4:
        sp = spr.blurred(st["blur"] * SS * 0.7)
    img = sp.mip(n) if n else sp.img
    h, w = img.shape[:2]; kk = k * (2 ** n); th = math.radians(el.rot + st["rot"]); c, s = math.cos(th), math.sin(th)
    hw, hh = w / 2, h / 2
    ox, oy = sx * rs, sy * rs
    sy = st.get("sy", 1.0)
    M = np.float32([[kk * c, -kk * s * sy, ox - kk * (c * hw - s * sy * hh)], [kk * s, kk * c * sy, oy - kk * (s * hw + c * sy * hh)]])
    corners = np.array([[0, 0], [w, 0], [w, h], [0, h]], np.float32); dst = corners @ M[:, :2].T + M[:, 2]
    x0, y0 = int(max(0, math.floor(dst[:, 0].min()))), int(max(0, math.floor(dst[:, 1].min())))
    x1, y1 = int(min(canvas.shape[1], math.ceil(dst[:, 0].max()) + 1)), int(min(canvas.shape[0], math.ceil(dst[:, 1].max()) + 1))
    if x1 <= x0 or y1 <= y0: return
    M2 = M.copy(); M2[0, 2] -= x0; M2[1, 2] -= y0
    roi = cv2.warpAffine(img, M2, (x1 - x0, y1 - y0), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    a = st["a"]
    if st["reveal"] is not None:
        p, soft = st["reveal"]; rw = roi.shape[1]; xs = (np.arange(rw) / max(1, rw - 1))
        ramp = np.clip((p * (1 + soft) - xs) / max(1e-3, soft), 0, 1)[None, :, None]; roi = roi * ramp
    if a < 0.999: roi = roi * a
    if el.blend == "add": canvas[y0:y1, x0:x1, :3] += roi[..., :3]; return
    _over(canvas[y0:y1, x0:x1], roi)
