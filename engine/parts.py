"""可复用的装饰部件:括号角标、挂锁、键帽、药丸标签、光标、窗口、文件图标等"""
from ci import *
from ci import _f

def load_rgb(name):
    im = cv2.imread(ASSETS + name, cv2.IMREAD_UNCHANGED)
    if im.shape[2] == 4:
        a = im[..., 3:4].astype(np.float32) / 255; rgb = im[..., :3].astype(np.float32) / 255 * a + 0.12 * (1 - a)
        return rgb[..., ::-1].copy()
    return (im[..., :3].astype(np.float32) / 255)[..., ::-1].copy()

# ---------- 文字
def giant(s, size, w=800, color=None, **k):
    grad = (CREAM, hexc("#A0988B"), 0.18, 0.88) if color is None else None
    return text_sprite(s, size, w, color or CREAM, grad=grad, shadow=(0, size * 0.06, size * 0.06, 0.55), **k)

def tag(s, size=22, color=STONE, tracking=0.2, w=500):
    return text_sprite(s.upper(), size, w, color, tracking=tracking)

def stagger(node, s, size, w, cx, cy, t0, step, anim, z=0.0, color=None, grad=None, shadow=True, **fmt):
    """逐字元素;返回元素列表。"""
    xs, tw = advances(s, size, w, fmt.get("tracking", 0.0), fmt.get("role") or False); left = cx - tw / 2; out = []
    for i, ch in enumerate(s):
        if ch == " ": continue
        kw = dict(fmt)
        if color is None and grad is None: kw["grad"] = (CREAM, hexc("#A0988B"), 0.18, 0.88)
        elif grad is not None: kw["grad"] = grad
        if shadow: kw["shadow"] = (0, size * 0.06, size * 0.06, 0.55)
        sp = text_sprite(ch, size, w, color or CREAM, **kw)
        cw = _f(ch, size, w, fmt.get('role') or False).getlength(ch)
        out.append(node.add(El(sp, left + xs[i] + cw / 2, cy, t0 + i * step, anim(), z=z)))
    return out

# ---------- 图形
def bracket(size=70, thick=6, color=STONE, corner="tl"):
    def d(dr, ss, im):
        n = int(size * ss); t = int(thick * ss); c = tuple(int(v * 255) for v in color) + (255,)
        pad = int(8 * ss)
        dr.rectangle((pad, pad, pad + n, pad + t), fill=c); dr.rectangle((pad, pad, pad + t, pad + n), fill=c)
    sp = raster_sprite(d, size + 16, size + 16)
    if corner != "tl":
        a = sp.img
        if corner in ("tr", "br"): a = a[:, ::-1]
        if corner in ("bl", "br"): a = a[::-1]
        sp = Sprite(np.ascontiguousarray(a), SS)
    return sp

def pill(text, size=26, fg=CREAM, bg=None, border=0.2, w=600, px=26, py=12, tracking=0.0, dot=None, icon=None, mono=False):
    tw = text_width(text, size, w, tracking, mono) + 2 * px + (size * 1.0 if dot else 0)
    h = size * 1.45 + 2 * py; ww = tw
    def d(dr, ss, im):
        col = (bg or (1, 1, 1))
        a = 255 if bg else int(255 * 0.07)
        dr.rounded_rectangle((8 * ss, 8 * ss, (ww + 8) * ss, (h + 8) * ss), h * ss / 2, fill=tuple(int(v * 255) for v in col) + (a,), outline=tuple(int(v * 255) for v in (fg if not bg else col)) + (int(255 * border),), width=max(1, int(1.5 * ss)))
        if dot: dr.ellipse(((px - 2) * ss + 8 * ss, (h / 2 - size * 0.22) * ss + 8 * ss, (px - 2 + size * 0.44) * ss + 8 * ss, (h / 2 + size * 0.22) * ss + 8 * ss), fill=tuple(int(v * 255) for v in dot) + (255,))
    base = raster_sprite(d, ww + 16, h + 16)
    t = text_sprite(text, size, w, fg, tracking=tracking, mono=mono, pad=2)
    # 把文字合到底图上
    ox = int((8 + px + (size * 1.0 if dot else 0)) * SS); oy = int((8 + py + size * 0.0) * SS)
    th, tw_ = t.img.shape[:2]; img = base.img.copy()
    y0 = int((8 + h / 2) * SS - th / 2 + size * 0.2 * SS * 0 - size * 0.075 * SS); x0 = ox - t.pad * SS if hasattr(t, "pad") else ox
    x0 = int(ox - 2 * SS)
    ys, xs_ = max(0, y0), max(0, x0); ye, xe = min(img.shape[0], y0 + th), min(img.shape[1], x0 + tw_)
    if ye > ys and xe > xs_:
        src = t.img[ys - y0:ye - y0, xs_ - x0:xe - x0]; dst = img[ys:ye, xs_:xe]; dst *= (1 - src[..., 3:4]); dst += src
    sp = Sprite(img, SS); return sp

def keycap(label, size=64, tilt=0):
    ww = max(size, text_width(label, size * 0.5, 600) + size * 0.7)
    def d(dr, ss, im):
        dr.rounded_rectangle((12 * ss, 10 * ss, (ww + 12) * ss, (size + 10) * ss), 14 * ss, fill=(52, 49, 46, 255), outline=(255, 255, 255, 46), width=int(2 * ss))
        dr.rounded_rectangle((12 * ss, 10 * ss, (ww + 12) * ss, (size - 6 + 10) * ss), 14 * ss, fill=(66, 62, 58, 255))
    base = raster_sprite(d, ww + 24, size + 28)
    # 阴影
    m = base.img[..., 3]; sh = soft_shadow(m, 0, 10 * SS, (0, 8 * SS), 0.55); img = np.zeros_like(base.img); img[..., 3] = sh
    img = img * (1 - base.img[..., 3:4]) + base.img
    t = text_sprite(label, size * 0.5, 600, CREAM, pad=2); th, tw = t.img.shape[:2]
    cx, cy = int((12 + ww / 2) * SS), int((10 + (size - 6) / 2) * SS - size * 0.03 * SS)
    y0, x0 = cy - th // 2 - int(size * 0.04 * SS), cx - tw // 2
    src = t.img; dst = img[y0:y0 + th, x0:x0 + tw]
    if dst.shape[:2] == src.shape[:2]: dst *= (1 - src[..., 3:4]); dst += src
    return Sprite(img, SS)

def padlock_parts(color=CREAM):
    bw, bh = 170, 130
    def body(dr, ss, im):
        dr.rounded_rectangle((20 * ss, 20 * ss, (20 + bw) * ss, (20 + bh) * ss), 26 * ss, fill=(232, 226, 214, 255))
        dr.ellipse(((20 + bw / 2 - 15) * ss, (20 + bh / 2 - 22) * ss, (20 + bw / 2 + 15) * ss, (20 + bh / 2 + 8) * ss), fill=(40, 36, 32, 255))
        dr.rounded_rectangle(((20 + bw / 2 - 5) * ss, (20 + bh / 2 - 5) * ss, (20 + bw / 2 + 5) * ss, (20 + bh / 2 + 34) * ss), 5 * ss, fill=(40, 36, 32, 255))
    b = raster_sprite(body, bw + 40, bh + 40)
    sw, shh, th = 112, 120, 24
    def shack(dr, ss, im):
        dr.arc((th * ss * 0.5 + 10 * ss, 10 * ss, (sw + th * 0.5 + 10) * ss, (sw + 10) * ss), 180, 360, fill=(214, 207, 194, 255), width=int(th * ss))
        dr.rectangle((10 * ss, (sw / 2 + 10) * ss, (10 + th) * ss, (shh + 10) * ss), fill=(214, 207, 194, 255))
        dr.rectangle(((sw + 10) * ss, (sw / 2 + 10) * ss, (sw + th + 10) * ss, (shh + 10) * ss), fill=(214, 207, 194, 255))
    s = raster_sprite(shack, sw + th + 20, shh + 20)
    return b, s, (bw, bh, sw + th, shh)

def cursor_sprite(size=64):
    def d(dr, ss, im):
        pts = [(6, 4), (6, 40), (15, 31), (22, 46), (29, 43), (22, 29), (35, 29)]
        pts = [(x * size / 52 * ss + 4 * ss, y * size / 52 * ss + 4 * ss) for x, y in pts]
        dr.polygon(pts, fill=(18, 18, 18, 255), outline=(255, 255, 255, 255)); dr.line(pts + [pts[0]], fill=(255, 255, 255, 255), width=int(3 * ss), joint="curve")
    sp = raster_sprite(d, size + 8, size + 8)
    m = sp.img[..., 3]; sh = soft_shadow(m, 0, 4 * SS, (2 * SS, 4 * SS), 0.5); img = sp.img * 1.0
    img = img + np.dstack([np.zeros_like(img[..., :3]), sh * (1 - img[..., 3])]); return Sprite(img, SS)

def ring_sprite(r=60, thick=5, color=ORANGE):
    def d(dr, ss, im):
        c = tuple(int(v * 255) for v in color) + (255,); dr.ellipse((8 * ss, 8 * ss, (2 * r + 8) * ss, (2 * r + 8) * ss), outline=c, width=int(thick * ss))
    return raster_sprite(d, 2 * r + 16, 2 * r + 16)

def A_ring(d=0.7, s0=0.3, s1=1.6):
    def f(t):
        p = E_OUT(t / d); return dict(a=(1 - clamp01(t / d)) ** 1.3, s=lerp(s0, s1, p))
    return f

def file_icon(label=".comp", w=150, h=190, color=ORANGE):
    def d(dr, ss, im):
        c = lambda v: int(v * ss)
        fold = 44
        pts = [(c(10), c(10)), (c(10 + w - fold), c(10)), (c(10 + w), c(10 + fold)), (c(10 + w), c(10 + h)), (c(10), c(10 + h))]
        dr.polygon(pts, fill=(236, 230, 220, 255))
        dr.polygon([(c(10 + w - fold), c(10)), (c(10 + w), c(10 + fold)), (c(10 + w - fold), c(10 + fold))], fill=(196, 188, 174, 255))
        dr.rounded_rectangle((c(10 + 22), c(10 + h - 70), c(10 + w - 22), c(10 + h - 26)), c(10), fill=tuple(int(v * 255) for v in color) + (255,))
        for i in range(3): dr.rounded_rectangle((c(10 + 22), c(10 + 56 + i * 20), c(10 + w - 22 - (i == 2) * 36), c(10 + 62 + i * 20)), c(3), fill=(150, 142, 130, 255))
    base = raster_sprite(d, w + 20, h + 20)
    m = base.img[..., 3]; sh = soft_shadow(m, 0, 12 * SS, (0, 12 * SS), 0.5); img = np.dstack([np.zeros_like(base.img[..., :3]), sh]) * (1 - base.img[..., 3:4]) + base.img
    t = text_sprite(label, 24, 700, hexc("#1B1814"), pad=2); th, tw = t.img.shape[:2]
    cx, cy = int((10 + w / 2) * SS), int((10 + h - 48) * SS); y0, x0 = cy - th // 2 - int(1 * SS), cx - tw // 2
    dst = img[y0:y0 + th, x0:x0 + tw]; src = t.img
    if dst.shape[:2] == src.shape[:2]: dst *= (1 - src[..., 3:4]); dst += src
    return Sprite(img, SS)

def checker_card(w, h, radius=18, cell=26, c1=(0.86, 0.86, 0.86), c2=(0.70, 0.70, 0.70), dark=False):
    ww, hh = int(w * SS), int(h * SS); cs = int(cell * SS)
    yy, xx = np.mgrid[0:hh, 0:ww]; chk = ((yy // cs + xx // cs) % 2).astype(np.float32)[..., None]
    if dark: c1, c2 = (0.20, 0.20, 0.21), (0.15, 0.15, 0.16)
    rgb = np.array(c1, np.float32) * (1 - chk) + np.array(c2, np.float32) * chk
    return card_from_rgb(rgb, w, radius)

def masked_cutout(rgb, mask, w):
    """抠图精灵:rgb + 软遮罩,带轮廓外阴影。"""
    h0, w0 = rgb.shape[:2]; k = int(w * SS) / w0; nw, nh = int(w0 * k), int(h0 * k)
    im = cv2.resize(rgb, (nw, nh), interpolation=cv2.INTER_AREA); m = cv2.resize(mask, (nw, nh), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
    pad = int(60 * SS); out = np.zeros((nh + 2 * pad, nw + 2 * pad, 4), np.float32)
    mm = np.zeros((nh + 2 * pad, nw + 2 * pad), np.float32); mm[pad:pad + nh, pad:pad + nw] = m
    sh = cv2.GaussianBlur(mm, (0, 0), 20 * SS); M = np.float32([[1, 0, 0], [0, 1, 26 * SS]]); sh = cv2.warpAffine(sh, M, (mm.shape[1], mm.shape[0])) * 0.6
    rgbp = np.zeros_like(out[..., :3]); rgbp[pad:pad + nh, pad:pad + nw] = im
    out[..., 3] = sh * (1 - mm) + mm; out[..., :3] = rgbp * mm[..., None]
    return Sprite(out, SS)

def tinted_mask(mask, w, color, alpha=0.35):
    h0, w0 = mask.shape[:2]; k = int(w * SS) / w0; nw, nh = int(w0 * k), int(h0 * k)
    m = cv2.resize(mask, (nw, nh), interpolation=cv2.INTER_AREA).astype(np.float32) / 255 * alpha
    out = np.zeros((nh, nw, 4), np.float32); out[..., :3] = np.array(color, np.float32) * m[..., None]; out[..., 3] = m
    return Sprite(out, SS)
