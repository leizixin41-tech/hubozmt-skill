"""背景 + 整帧合成 + 后期"""
from ci import *

# ---------------- 背景
_yy, _xx = np.mgrid[0:H, 0:W].astype(np.float32)
_RD = np.hypot((_xx - W / 2) / (W * 0.5), (_yy - H / 2) / (H * 0.5))
BASE_C = np.array(hexc("#232225"), np.float32); BASE_E = np.array(hexc("#0B0B0C"), np.float32)
_t = np.clip(_RD / 1.35, 0, 1)[..., None] ** 1.5
BASE = (BASE_C * (1 - _t) + BASE_E * _t).astype(np.float32)
VIGN = (1.0 - 0.38 * np.clip(_RD - 0.45, 0, 1.3) ** 1.7)[..., None].astype(np.float32)
_rg = np.random.RandomState(7)
GRAINS = [(_rg.normal(0, 1, (H // 2, W // 2, 1)) * 0.016).astype(np.float32) for _ in range(6)]
# 窗格光影(斜条,宽场)
_gx = (_xx + _yy * 0.55)
def gobo(off):
    v = np.sin((_gx + off) / 520.0 * math.pi) * 0.5 + 0.5
    v = np.clip((v - 0.45) / 0.5, 0, 1); v = v * v * (3 - 2 * v)
    return v[..., None]
_lowx, _lowy = np.mgrid[0:H // 4, 0:W // 4].astype(np.float32)

def background(t, cam, blobs, style=None):
    cx, cy, cz = cam
    if style is not None:
        blobs = style['blobs']; tt = np.clip(_RD / 1.35, 0, 1)[..., None] ** 1.5
        f = (np.array(style['base_c'], np.float32) * (1 - tt) + np.array(style['base_e'], np.float32) * tt).astype(np.float32)
        gb, dm = style['gobo'], style['dots']
    else:
        f = BASE.copy(); gb, dm = 0.040, 0.07
    f += gb * gobo(t * 30.0 - cx * 0.12)                                    # 窗格光影,缓慢扫过
    # 彩色光斑(视差 0.35):在 1/4 分辨率里画
    acc = np.zeros((H // 4, W // 4, 3), np.float32)
    for (bx, by, col, rad, amp) in blobs:
        sx = ((bx - cx) * 0.35 * cz) + W / 2; sy = ((by - cy) * 0.35 * cz) + H / 2
        if sx < -rad * 1.6 or sx > W + rad * 1.6 or sy < -rad * 1.6 or sy > H + rad * 1.6: continue
        d2 = ((_lowx * 4 - sy) ** 2 + (_lowy * 4 - sx) ** 2) / (rad * rad)
        g = np.exp(-d2 * 1.2) * amp * 0.6; acc += g[..., None] * np.array(col, np.float32)
    f += cv2.resize(acc, (W, H), interpolation=cv2.INTER_LINEAR)
    # 点阵(视差 0.5),半分辨率
    s = 72.0; ox = (-(cx * 0.5 * cz)) % s; oy = (-(cy * 0.5 * cz)) % s
    xs = (np.arange(W // 2, dtype=np.float32) * 2 + ox) % s - s / 2; ys = (np.arange(H // 2, dtype=np.float32) * 2 + oy) % s - s / 2
    r = np.hypot(xs[None, :], ys[:, None]); dots = np.clip(1.6 - r / 1.1, 0, 1) * dm
    f += cv2.resize(dots, (W, H), interpolation=cv2.INTER_LINEAR)[..., None]
    return f

# ---------------- 整帧
def node_visible(node, t):
    return t >= node.t_in - node.flight - node.lead

def render_frame(scene, fi):
    t = fi / FPS
    cam = scene.camera(t); Ls = scene.levels(t); FD = scene.fades(t)
    sty = scene.style(t) if hasattr(scene, 'style') else None
    frame = background(t, cam, scene.bg, sty)
    for node, L, fd in zip(scene.nodes, Ls, FD):
        if not node_visible(node, t) or (fd <= 0.002 if scene.old_fade else L >= 3.0): continue
        sigma = 10.0 * min(L, 1.0) + 12.0 * clamp01(L - 1.0)
        dim = 1.0 - 0.60 * min(L, 1.0) - 0.22 * clamp01(L - 1.0)
        alpha_n = fd if scene.old_fade else (1.0 - smooth(L - 2.0))
        push = 1.0 - 0.06 * min(L, 2.0)
        # 节点是否在视野附近
        d = np.hypot((node.pos[0] - cam[0]) * cam[2], (node.pos[1] - cam[1]) * cam[2])
        if d > 3600: continue
        rs = 1.0 if sigma < 2.0 else (0.5 if sigma < 7.0 else 0.25)
        cv_ = np.zeros((int(H * rs), int(W * rs), 4), np.float32)
        for el in node.els:
            st = el.state(t - node.shift - (node.toff if el.ui else 0.0))
            if st is not None: draw_el(cv_, el, st, node.pos, cam, rs, push)
        if sigma > 0.3: cv_ = cv2.GaussianBlur(cv_, (0, 0), sigma * rs)
        if rs < 1.0: cv_ = cv2.resize(cv_, (W, H), interpolation=cv2.INTER_LINEAR)
        if dim < 0.999:
            lum = cv_[..., :3].mean(-1, keepdims=True); sat = 1.0 - 0.45 * min(L, 1.0)
            cv_[..., :3] = (cv_[..., :3] * sat + lum * (1 - sat)) * dim
        cv_ *= alpha_n
        frame = cv_[..., :3] + frame * (1 - cv_[..., 3:4])
    # 后期
    if sty is not None:
        vg = (1.0 - sty['vign'] * np.clip(_RD - 0.45, 0, 1.3) ** 1.7)[..., None].astype(np.float32); frame *= vg; gk = sty['grain'] / 0.016
    else:
        frame *= VIGN; gk = 1.0
    g = cv2.resize(GRAINS[fi % 6], (W, H), interpolation=cv2.INTER_LINEAR)[..., None] * gk
    frame += g * (0.6 + 0.4 * (1 - frame.mean(-1, keepdims=True)))
    fade = min(1.0, t / 0.25) * min(1.0, max(0.0, (scene.duration - t) / 0.6))
    frame *= fade
    return (np.clip(frame, 0, 1) * 255 + 0.5).astype(np.uint8)[..., ::-1]
