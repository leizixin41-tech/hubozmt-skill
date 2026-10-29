"""hubozmt 场景组件包:节点、版面登记、文字/卡片/截图、常用动效组件、版面检查。
场景脚本只需 `from kit import *`。用法速查见 API.md。"""
from parts import *
from ci import _f, _fontlib
import json, sys

VIOLET = hexc("#9B7BFF"); VIOLET2 = hexc("#C9B8FF"); VIOLET_D = hexc("#6A4DE0")
SANS, GROT, MONO_ = "sans", "grot", "mono"            # 字体库角色名

nodes = []
def node(name, t_in, pos=(0, 0), zoom=1.0, fixed=False, **k):
    """新建节点(画布上的一处内容)。t_in=镜头到位时刻;fixed=True 时用你给的 pos,否则由 finish() 自动排布。"""
    n = Node(name, t_in, pos, zoom, **k); n._rects = []; n._blobs = []; n._fixed = fixed; nodes.append(n); return n

def reg(node, kind, x, y, w, h, label=""):
    """登记一个占位矩形(局部坐标,中心 x,y)。kind: text / card / deco"""
    node._rects.append((kind, x - w / 2, y - h / 2, x + w / 2, y + h / 2, label))

def blob(node, dx, dy, c, r=900, a=0.10): node._blobs.append((dx, dy, c, r, a))

# ------------------------------------------------------------ 素材
def shot(name, crop=None, w=600, radius=14, chrome=None, title=None, shadow=(60, 40, 26, 0.7)):
    im = cv2.imread(ASSETS + name)[..., ::-1]
    if crop: x0, y0, x1, y1 = crop; im = im[y0:y1, x0:x1]
    return card_from_rgb(np.ascontiguousarray(im), w, radius, shadow, 0.10, chrome=chrome, title=title)

def card_el(node, sp, x, y, t0, anim, z=0.0, **k):
    """放置卡片并登记版面(扣掉阴影留白)。"""
    pad = getattr(sp, "pad", 0)
    reg(node, "card", x, y, sp.dw - 2 * pad, sp.dh - 2 * pad, "card")
    return node.add(El(sp, x, y, t0, anim, z=z, **k))

def icon_sprite(w, name):
    """带透明通道的图标(如应用图标)→ 带柔和投影的精灵。name 为本期 assets/ 下的文件名。"""
    ICON = cv2.imread(ASSETS + name, cv2.IMREAD_UNCHANGED)
    if ICON.shape[2] == 3: ICON = cv2.cvtColor(ICON, cv2.COLOR_BGR2BGRA)
    rgba = cv2.cvtColor(ICON, cv2.COLOR_BGRA2RGBA).astype(np.float32) / 255
    k = int(w * SS) / rgba.shape[1]; im = cv2.resize(rgba, (int(rgba.shape[1] * k), int(rgba.shape[0] * k)), interpolation=cv2.INTER_AREA)
    pad = int(70 * SS); h, ww = im.shape[:2]; out = np.zeros((h + 2 * pad, ww + 2 * pad, 4), np.float32)
    a = np.zeros(out.shape[:2], np.float32); a[pad:pad + h, pad:pad + ww] = im[..., 3]
    sh = soft_shadow(im[..., 3], pad, 28 * SS, (0, 24 * SS), 0.65)
    out[..., 3] = sh; rgbp = np.zeros_like(out[..., :3]); rgbp[pad:pad + h, pad:pad + ww] = im[..., :3] * im[..., 3:4]
    out[..., :3] = out[..., :3] * (1 - a[..., None]) + rgbp; out[..., 3] = out[..., 3] * (1 - a) + a
    sp = Sprite(out, SS); sp.pad = 70; return sp

# ------------------------------------------------------------ 文字
def _check(role, s):
    miss = _fontlib.has_glyphs(role or "sans", s)
    if miss: raise SystemExit(f"字体缺字:角色 {role!r} 缺 {miss}(文字 {s!r})——换一个角色")

def big(node, s, size, w, cx, cy, t0, step, anim, role=SANS, z=0.0, color=None, grad=None, **fmt):
    """逐字大字,并登记版面。"""
    _check(role, s)
    tr = fmt.get("tracking", 0.0); _, tw = advances(s, size, w, tr, role)
    reg(node, "text", cx, cy, tw, size * 1.05, s)
    return stagger(node, s, size, w, cx, cy, t0, step, anim, z=z, color=color, grad=grad, role=role, **fmt)

def line(node, s, size, w, color, cx, cy, t0, anim, role=SANS, z=0.0, tracking=0.0, shadow=None, kind="text"):
    """整行文字(单个精灵)。"""
    _check(role, s)
    sp = text_sprite(s, size, w, color, tracking=tracking, role=role, shadow=shadow)
    reg(node, kind, cx, cy, sp.tw, size * 1.05, s)
    return node.add(El(sp, cx, cy, t0, anim, z=z))

def tag2(node, s, size, color, cx, cy, t0, tracking=0.3, w=500, role=GROT, anim=None, z=0.1):
    _check(role, s.upper())
    sp = text_sprite(s.upper(), size, w, color, tracking=tracking, role=role)
    reg(node, "text", cx, cy, sp.tw, size * 1.1, s)
    return node.add(El(sp, cx, cy, t0, anim or A_wipe(0.6), z=z))

def pill_el(node, s, cx, cy, t0, size=30, fg=CREAM, bg=None, w=600, px=28, dot=None, anim=None, z=0.3, role=SANS, tracking=0.0):
    _check(role, s)
    sp = pill(s, size, fg, bg=bg, w=w, px=px, tracking=tracking, dot=dot, mono=role)
    reg(node, "text", cx, cy, sp.dw - 16, sp.dh - 16, "pill:" + s)
    return node.add(El(sp, cx, cy, t0, anim or A_pop(0.5), z=z))

def deco(node, sp, x, y, t0, anim, z=-0.5, **k):
    """装饰元素(角标、线条、光点等):不参与重叠检查,也不计入「展示完整」检查。"""
    reg(node, "deco", x, y, sp.dw, sp.dh, "deco"); return node.add(El(sp, x, y, t0, anim, z=z, name="deco", **k))

def sparkle(size, color, n=4, inner=0.22):
    def d(dr, ss, im):
        c = size / 2 * ss + 8 * ss; r = size / 2 * ss; pts = []
        for i in range(n * 2):
            ang = -math.pi / 2 + i * math.pi / n; rr = r if i % 2 == 0 else r * inner
            pts.append((c + rr * math.cos(ang), c + rr * math.sin(ang)))
        dr.polygon(pts, fill=tuple(int(v * 255) for v in color) + (255,))
    return raster_sprite(d, size + 16, size + 16)

def star5(size, color):
    def d(dr, ss, im):
        c = size / 2 * ss + 8 * ss; r = size / 2 * ss; pts = []
        for i in range(10):
            ang = -math.pi / 2 + i * math.pi / 5; rr = r if i % 2 == 0 else r * 0.40
            pts.append((c + rr * math.cos(ang), c + rr * math.sin(ang)))
        dr.polygon(pts, fill=tuple(int(v * 255) for v in color) + (255,))
    return raster_sprite(d, size + 16, size + 16)

def arrow_sprite(w, color, thick=10):
    h = 70
    def d(dr, ss, im):
        c = tuple(int(v * 255) for v in color) + (255,); y = (h / 2 + 8) * ss
        dr.rounded_rectangle((8 * ss, y - thick / 2 * ss, (w - 26 + 8) * ss, y + thick / 2 * ss), thick / 2 * ss, fill=c)
        dr.polygon([((w - 36 + 8) * ss, y - 24 * ss), ((w + 8) * ss, y), ((w - 36 + 8) * ss, y + 24 * ss)], fill=c)
    return raster_sprite(d, w + 16, h + 16)

def typed(node, s, x_left, cy, t0, step, size=40, w=500, color=INK, z=0.0, role=SANS, caret=True, t_end=None):
    """逐字打出 + 闪烁光标。"""
    _check(role, s)
    xs, tw = advances(s, size, w, 0.0, role)
    for i, ch in enumerate(s):
        sp = text_sprite(ch, size, w, color, role=role, pad=4)
        cw = _f(ch, size, w, role).getlength(ch)
        node.add(El(sp, x_left + xs[i] + cw / 2, cy, t0 + i * step, A_fade(0.05), z=z))
    if caret:
        tt1 = t0 + len(s) * step
        cs = flat_card(5, size * 1.25, VIOLET, 2, shadow=None, border=0)
        def cc(t, xs=xs, tw=tw):
            n_ = max(0, min(len(s), int((t - t0) / step + 1))); x = x_left + (xs[n_] if n_ < len(s) else tw) + 5
            return dict(dx=x - x_left, a=0.35 + 0.65 * (math.sin(t * 16) > 0))
        node.add(El(cs, x_left, cy, t0 - 0.1, None, z=z, custom=cc, t1=t_end))

def ui_input_card(w, h, label):
    """自绘的浅色输入框卡片(概念示意,不是截图)。"""
    ss = 2; img = Image.new("RGB", (w * ss, h * ss), (247, 245, 240)); d = ImageDraw.Draw(img)
    d.text((34 * ss, 30 * ss), label, font=_f("用", 26 * ss, 500), fill=(120, 116, 108))
    d.rounded_rectangle((30 * ss, 84 * ss, (w - 30) * ss, (h - 30) * ss), 14 * ss, fill=(255, 255, 253), outline=(224, 220, 210), width=2 * ss)
    im = np.asarray(img.resize((w, h), Image.LANCZOS), np.float32) / 255
    return card_from_rgb(im, w, 20, (60, 40, 26, 0.7), 0.10)

# ============================================================ 版面:按版面大小排布节点,使相邻节点互不压盖
AXIS = "x" if W >= H else "y"          # 横屏沿 x 排布,竖屏沿 y 排布

def layout(gap=110, wobble=(0, 150, -120, 120, -150, 90, -100, 140, -80)):
    """自动排布:没有用 fixed=True 的节点,按顺序沿 AXIS 排开,另一方向按 wobble 轻微错落。"""
    prev = None
    for i, n in enumerate(nodes):
        if getattr(n, "_fixed", False): prev = n; continue
        R = [r for r in n._rects if r[0] not in ("deco", "full")] or [("x", -100, -100, 100, 100, "")]
        lo = min(r[1] for r in R) if AXIS == "x" else min(r[2] for r in R)
        if prev is None: main = 0.0
        else:
            PR = [r for r in prev._rects if r[0] not in ("deco", "full")] or [("x", -100, -100, 100, 100, "")]
            hi_prev = (max(r[3] for r in PR) + prev.pos[0]) if AXIS == "x" else (max(r[4] for r in PR) + prev.pos[1])
            main = hi_prev + gap - lo
        side = float(wobble[i % len(wobble)]) if wobble else 0.0
        n.pos = np.array([main, side]) if AXIS == "x" else np.array([side * 0.5, main])
        prev = n

def finish(auto_layout=True):
    """场景脚本最后调用:排布节点并返回背景光斑列表。用法: BLOBS = finish()"""
    if auto_layout: layout()
    bl = []
    for n in nodes:
        for (dx, dy, c, r, a) in n._blobs: bl.append((n.pos[0] + dx, n.pos[1] + dy, c, r, a))
    return bl

def draw_aa(canvas, mask_fn, color, alpha=1.0, blur=0.0):
    m = np.zeros(canvas.shape[:2], np.uint8); mask_fn(m)
    if m.max() == 0: return
    a = m.astype(np.float32) / 255 * alpha
    if blur > 0: a = cv2.GaussianBlur(a, (0, 0), blur)
    src = np.dstack([np.array(color, np.float32) * a[..., None], a]); canvas *= (1 - src[..., 3:4]); canvas += src

def check_layout(verbose=True):
    """出片前检查:同节点内 文字/卡片/文字 不重叠;节点放得进画面;相邻节点互不压盖。返回问题列表。"""
    bad = []
    for n in nodes:
        R = [r for r in n._rects if r[0] not in ("deco", "full")]
        for i in range(len(R)):
            for j in range(i + 1, len(R)):
                a, b = R[i], R[j]
                if a[0] == "card" and b[0] == "card": continue
                ox = min(a[3], b[3]) - max(a[1], b[1]); oy = min(a[4], b[4]) - max(a[2], b[2])
                if ox > 0 and oy > 0: bad.append(f"[{n.name}] 重叠 {a[5]!r} × {b[5]!r}({ox:.0f}×{oy:.0f}px)")
        allr = [r for r in n._rects if r[0] not in ("deco", "full")]
        hw = W / 2 / n.zoom - 40; hh = H / 2 / n.zoom - 40
        for r in allr:
            if r[1] < -hw or r[3] > hw or r[2] < -hh or r[4] > hh: bad.append(f"[{n.name}] 超出画面 {r[5]!r}  x[{r[1]:.0f},{r[3]:.0f}] y[{r[2]:.0f},{r[4]:.0f}] 允许 ±{hw:.0f}×±{hh:.0f}")
    def box(n):
        R = [r for r in n._rects if r[0] not in ("deco", "full")]
        if not R: return None
        return (min(r[1] for r in R) + n.pos[0], min(r[2] for r in R) + n.pos[1], max(r[3] for r in R) + n.pos[0], max(r[4] for r in R) + n.pos[1])
    for a, b in zip(nodes, nodes[1:]):
        A, B = box(a), box(b)
        if A and B and min(A[2], B[2]) - max(A[0], B[0]) > -60 and min(A[3], B[3]) - max(A[1], B[1]) > -60:
            bad.append(f"相邻节点压盖或太近 {a.name}→{b.name}")
    # 展示完整:节点里最后一个元素出现后,至少留 0.6 秒再起镜飞走
    for a, b in zip(nodes, nodes[1:]):
        last = max((e.t0 for e in a.els if e.name != "deco"), default=a.t_in); leave = b.t_in - b.flight * b.pre
        if leave - last < 0.6: bad.append(f"[{a.name}] 最后一个元素 {last:.2f}s 出现,{leave:.2f}s 镜头就离开,展示不足 0.6 秒")
    if verbose: print("\n".join(bad) if bad else "版面检查通过:无文字被遮挡、节点互不压盖、每段展示完整")
    return bad


# ============================================================ 动效组件
def strip_card(node, name, crop, w, cx, cy, t0, step=0.07, title=None, z=0.3, plate_anim=None, line_anim=None):
    """截图按文字行切条,先出底板,再一行一行出现(表现「结构」被写出来)。"""
    im = cv2.imread(ASSETS + name)[..., ::-1]; x0, y0, x1, y1 = crop; im = np.ascontiguousarray(im[y0:y1, x0:x1])
    bg = np.median(im.reshape(-1, 3), 0)
    rows = (np.abs(im.astype(int) - bg).sum(2) > 40).any(1)
    bands, i = [], 0
    while i < len(rows):
        if rows[i]:
            j = i
            while j < len(rows) and rows[j]: j += 1
            if bands and i - bands[-1][1] < 5: bands[-1][1] = j
            else: bands.append([i, j])
            i = j
        else: i += 1
    k = w / im.shape[1]; h = im.shape[0] * k; bar = 38 if title else 0
    plate = np.empty(im.shape, np.float32); plate[:] = bg / 255
    psp = card_from_rgb(plate, w, 14, (60, 40, 26, 0.7), 0.10, chrome="mac" if title else None, title=title)
    reg(node, "card", cx, cy, psp.dw - 2 * psp.pad, psp.dh - 2 * psp.pad, "card")
    node.add(El(psp, cx, cy, t0, plate_anim or A_rise(0.6, 30, blur=6), z=z))
    top = cy - (h + bar) / 2 + bar
    for n_, (a, b) in enumerate(bands):
        a = max(0, a - 3); b = min(im.shape[0], b + 3)
        sp = card_from_rgb(np.ascontiguousarray(im[a:b]).astype(np.float32) / 255, w, 0, None, 0)
        node.add(El(sp, cx, top + (a + b) / 2 * k, t0 + 0.35 + n_ * step, (line_anim or (lambda: A_rise(0.45, 14, blur=4)))(), z=z))
    return len(bands)

def type_delete(node, s, cx, cy, t0, step, td, dstep, size, w, color, t_end):
    """逐字打出,停顿,再逐字删掉(表现「不会写」)。"""
    xs, tw = advances(s, size, w, 0.0, False); left = cx - tw / 2; n = len(s)
    reg(node, "text", cx, cy, tw, size * 1.1, s)
    for i, ch in enumerate(s):
        sp = text_sprite(ch, size, w, color, pad=4); cw = _f(ch, size, w, False).getlength(ch)
        node.add(El(sp, left + xs[i] + cw / 2, cy, t0 + i * step, A_fade(0.04), t1=td + (n - 1 - i) * dstep, fade_out=0.03))
    cs = flat_card(4, size * 1.25, VIOLET, 2, shadow=None, border=0)
    def cc(t):
        if t < td: kk = max(0, min(n, int((t - t0) / step) + 1))
        else: kk = max(0, n - int((t - td) / dstep) - 1)
        x = xs[kk] if kk < n else tw
        return dict(dx=x + 3, a=0.35 + 0.65 * (math.sin(t * 15) > 0))
    node.add(El(cs, left, cy, t0 - 0.15, None, custom=cc, t1=t_end))

def hl(w, h, color, width=5, r=12):
    def d(dr, ss, im): dr.rounded_rectangle((8 * ss, 8 * ss, (w + 8) * ss, (h + 8) * ss), r * ss, outline=tuple(int(v * 255) for v in color) + (255,), width=int(width * ss))
    return raster_sprite(d, w + 16, h + 16)

def timer_el(node, x, y, r, t0, d, color):
    def p(canvas, f, k, st):
        tl = st["t"] - t0
        if tl < 0: return
        prog = E_INOUT(tl / d); X, Y = f(0, 0); R = r * k; th = max(1, int(round(6 * k)))
        c = (int(X * 16), int(Y * 16)); ax = (int(R * 16), int(R * 16))
        draw_aa(canvas, lambda m: cv2.ellipse(m, c, ax, 0, 0, 360, 255, th, cv2.LINE_AA, 4), color, 0.22)
        if prog > 0.002: draw_aa(canvas, lambda m: cv2.ellipse(m, c, ax, 0, -90, -90 + 360 * prog, 255, th, cv2.LINE_AA, 4), color, 1.0)
        hx, hy = f(math.sin(prog * TAU) * r * 0.62, -math.cos(prog * TAU) * r * 0.62)
        draw_aa(canvas, lambda m: cv2.line(m, (int(X * 16), int(Y * 16)), (int(hx * 16), int(hy * 16)), 255, th, cv2.LINE_AA, 4), color, 1.0)
    reg(node, "text", x, y, 2 * r + 12, 2 * r + 12, "timer")
    node.add(El(None, x, y, t0 - 0.05, A_fade(0.2), z=0.3, paint=p))

def check_el(node, x, y, size, t0, d, color):
    P = np.array([(-0.45, 0.0), (-0.12, 0.32), (0.48, -0.36)]) * size
    def p(canvas, f, k, st):
        tl = st["t"] - t0
        if tl < 0: return
        prog = E_OUT(tl / d); seg = np.linalg.norm(P[1] - P[0]); tot = seg + np.linalg.norm(P[2] - P[1]); L = prog * tot
        pts = [P[0]]
        if L <= seg: pts.append(P[0] + (P[1] - P[0]) * L / seg)
        else: pts += [P[1], P[1] + (P[2] - P[1]) * (L - seg) / (tot - seg)]
        Q = np.array([f(px, py) for px, py in pts]) * 16
        draw_aa(canvas, lambda m: cv2.polylines(m, [np.round(Q).astype(np.int32)], False, 255, max(1, int(9 * k)), cv2.LINE_AA, 4), color, 1.0)
    reg(node, "text", x, y, size * 1.1, size * 0.8, "check")
    node.add(El(None, x, y, t0, A_fade(0.05), z=0.4, paint=p))

def vbar(h, color, w=4): return flat_card(w, h, color, w / 2, shadow=None, border=0)
def A_grow_y(d=0.7):
    return lambda t: dict(a=clamp01(t / 0.15), sy=max(0.01, E_OUT(t / d)))


# ------------------------------------------------------------ 数字滚动(里程表)
def odometer(node, value, x, y, size, t0, t1, color=CREAM, grad=None, role=GROT, weight=800, roll=None):
    """整数 value 从 0 滚到目标值;每一位独立滚动(低位连续滚,高位进位时滚)。返回整组宽度。"""
    digits = str(int(value)); n = len(digits)
    sp = {d: text_sprite(str(d), size, weight, color, grad=grad if grad else (CREAM, hexc("#8E877B"), 0.2, 0.88), shadow=(0, size * 0.05, size * 0.05, 0.55), role=role) for d in range(10)}
    adv = _f("0", size, weight, role).getlength("0") * 0.98; total = adv * n; roll = roll or size * 0.33
    xs = [x - total / 2 + adv * (i + 0.5) for i in range(n)]
    def draw(canvas, f, k, d, off, al, xi):
        s_ = sp[d % 10]; img = s_.img; cx_, cy_ = f(xi - x, off * roll); kk = k / s_.ss
        M = np.float32([[kk, 0, cx_ - kk * img.shape[1] / 2], [0, kk, cy_ - kk * img.shape[0] / 2]])
        roi = cv2.warpAffine(img, M, (canvas.shape[1], canvas.shape[0]), flags=cv2.INTER_LINEAR) * al
        canvas *= (1 - roi[..., 3:4]); canvas += roi
    def paint(canvas, f, k, st):
        v = value * E_EXPO((st["t"] - t0) / max(1e-3, t1 - t0))
        for i in range(n):
            p = 10 ** (n - 1 - i); base = int(math.floor(v / p)); cap = int(value // p)
            fr = (v - math.floor(v)) if p == 1 else smooth(clamp01((v % p) - (p - 1)))
            for d, off, al in ((base, -fr, 1 - fr), (base + 1, 1 - fr, fr)):
                if al > 0.01 and d <= cap: draw(canvas, f, k, d, off, al, xs[i])
    reg(node, "text", x, y, total, size * 0.78, "odometer")
    node.add(El(None, x, y, t0 - 0.1, A_fade(0.15), paint=paint))
    return total

def slide_dim(dx, t0_, t_dim=None, dim=0.55):
    """从侧面滑入;到 t_dim 时变暗(用于「优化前 / 优化后」对比)。"""
    base = A_rise(0.8, 0, blur=8, dx=dx)
    def f(t):
        st = base(t)
        if t_dim is not None: st["a"] *= 1 - dim * smooth((t + t0_ - t_dim) / 0.5)
        return st
    return f


# ------------------------------------------------------------ 视频图层(真人口播画面等)
_VCAP = {}
def _vframe(path, t):
    """取视频在 t 秒的画面(RGB float 0..1)。每个进程各自缓存,顺序读取时不重复跳转。"""
    c = _VCAP.get(path)
    if c is None:
        cap = cv2.VideoCapture(path); c = _VCAP[path] = dict(cap=cap, fps=cap.get(cv2.CAP_PROP_FPS) or 30, n=int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), i=-1, img=None)
    idx = max(0, min(c["n"] - 1, int(round(t * c["fps"]))))
    if idx != c["i"]:
        if idx != c["i"] + 1: c["cap"].set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, fr = c["cap"].read()
        if ok: c["img"] = cv2.cvtColor(fr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255
        c["i"] = idx
    return c["img"]

def video_el(node, path, x, y, w, h=None, t0=0.0, src_t0=None, dur=None, radius=18, anim=None, z=0.0, focus=(0.5, 0.5), border=0.12, t1=None):
    """在画布上放一段视频,画面时间与成片时间同步走。
    path:视频文件(通常是本期 work/video_cut.mp4 或 work/video.mp4);相对路径按本期文件夹解析。
    w,h:设计尺寸;h 省略时按视频原比例。给了 h 且比例不同 → 按 focus(相对坐标,如人脸位置)居中裁切铺满。
    src_t0:元素出现时对应视频的第几秒;省略 = t0(用剪过气口的视频时,画面与口播天然同步)。
    整屏真人:w = W / node.zoom,h = H / node.zoom,radius=0。"""
    ep = os.environ.get("HZ_EPISODE", "")
    if not os.path.isabs(path): path = os.path.join(ep, path)
    cap = cv2.VideoCapture(path); sw, sh = int(cap.get(3)), int(cap.get(4)); cap.release()
    if not sw: raise SystemExit(f"打不开视频: {path}")
    h = h or w * sh / sw; src_t0 = t0 if src_t0 is None else src_t0
    ta, tb = sw / sh, w / h                                   # 裁切到目标比例
    if ta > tb: cw, ch = int(sh * tb), sh
    else: cw, ch = sw, int(sw / tb)
    cx0 = int(min(sw - cw, max(0, focus[0] * sw - cw / 2))); cy0 = int(min(sh - ch, max(0, focus[1] * sh - ch / 2)))
    mask = rrect_mask(cw, ch, radius * cw / w)[..., None] if radius > 0 else None
    def paint(canvas, f, k, st):
        tt = src_t0 + (st["t"] - t0)
        if dur is not None and st["t"] - t0 > dur: return
        img = _vframe(path, tt)
        if img is None: return
        img = img[cy0:cy0 + ch, cx0:cx0 + cw]
        a = mask if mask is not None else np.ones((ch, cw, 1), np.float32)
        if border and radius > 0:
            er = cv2.erode(a[..., 0], np.ones((3, 3), np.uint8))[..., None]; img = img * (1 - (a - er) * border) + (a - er) * border
        rgba = np.concatenate([img * a, a], 2) * st["a"]
        kk = k * w / cw; X, Y = f(0, 0)
        M = np.float32([[kk, 0, X - kk * cw / 2], [0, kk, Y - kk * ch / 2]])
        x0, y0 = int(max(0, X - kk * cw / 2 - 2)), int(max(0, Y - kk * ch / 2 - 2))
        x1, y1 = int(min(canvas.shape[1], X + kk * cw / 2 + 2)), int(min(canvas.shape[0], Y + kk * ch / 2 + 2))
        if x1 <= x0 or y1 <= y0: return
        M[0, 2] -= x0; M[1, 2] -= y0
        roi = cv2.warpAffine(rgba, M, (x1 - x0, y1 - y0), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
        sub = canvas[y0:y1, x0:x1]; sub *= (1 - roi[..., 3:4]); sub += roi
    full = w >= W / node.zoom - 2 and h >= H / node.zoom - 2         # 整屏视频:不参与重叠/越界检查,上面可以压字
    reg(node, "full" if full else "card", x, y, w, h, "video")
    return node.add(El(None, x, y, t0, anim or A_fade(0.3), z=z, paint=paint, t1=t1, name="video"))
