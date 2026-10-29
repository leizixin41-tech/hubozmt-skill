#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dissect.py — 参考视频拆解器。把一段视频拆成可复现的"设计规格"。

输出(OUTDIR):
  report.md      拆解报告(镜头运动+缓动拟合 / 元素动效事件 / 屏幕文字轨迹 / 配色 / 音频节奏 / 合并时间线)
  data.json      同一份数据的机器可读版
  timeline.png   一张图看全片:镜头速度、元素动效、文字寿命、音频包络与重音
  sheets/        总览联系表(带时间戳)
  moves/         每次镜头运动的 8 帧条带
  events/        每个元素动效的局部放大条带(裁剪到动效发生的区域)
  motion.npz     逐帧原始运动数据(调试/复核用)

用法: python3 dissect.py VIDEO OUTDIR [--ocr-fps 4] [--no-ocr] [--no-cuts] [--no-audio] [--no-images] [--max-events 40]
依赖: ffmpeg/ffprobe, numpy, opencv(-headless), Pillow;可选: scenedetect(切点), rapidocr_onnxruntime(文字)
方法:  角点 LK 光流 + 前后向校验 + 顺序 RANSAC 分层(每层=平移+缩放[+旋转]) → 前景/视差层/静态叠层;
       运动补偿后的局部帧差 → 元素动效事件; 累计位移曲线 → 三次贝塞尔缓动拟合。
"""
import argparse, difflib, json, math, os, shutil, subprocess, sys, time
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont

T0 = time.time()
def LOG(*a): print("[dissect %6.1fs]" % (time.time() - T0), *a, flush=True)
def run(cmd): return subprocess.run(cmd, capture_output=True, check=True)
def hexc(bgr): b, g, r = [int(round(float(x))) for x in list(bgr)[:3]]; return "#%02x%02x%02x" % (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))
def fmt_t(t): return "%d:%05.2f" % (int(t // 60), t % 60)
def lum_of(bgr): b, g, r = [float(x) for x in list(bgr)[:3]]; return 0.2126 * r + 0.7152 * g + 0.0722 * b

def _font_candidates():
    """标注文字用的字体,按顺序取第一个能打开的:环境变量 DISSECT_FONT > 项目自带思源黑体 > 各系统常见中文字体 > DejaVu(无中文字形,仅保证不崩)"""
    here = os.path.dirname(os.path.abspath(__file__))
    c = [os.environ.get("DISSECT_FONT", ""), os.path.join(here, "..", "library", "字体库", "NotoSansSC", "NotoSansSC-Regular.otf"),
         "/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/STHeiti Medium.ttc", "/System/Library/Fonts/Hiragino Sans GB.ttc", "/Library/Fonts/Arial Unicode.ttf",   # macOS
         "C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyh.ttf", "C:/Windows/Fonts/simhei.ttf", "C:/Windows/Fonts/simsun.ttc",                                           # Windows
         "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]                                                                                                                 # Linux
    return [p for p in c if p]
FONT_PATHS = _font_candidates()
_FC = {}
def font(sz):
    if sz not in _FC:
        for p in FONT_PATHS:
            if os.path.exists(p):
                try: _FC[sz] = ImageFont.truetype(p, sz); break
                except Exception: pass
        else: _FC[sz] = ImageFont.load_default()
    return _FC[sz]

# ======================================================================== 基本信息
def probe(video):
    j = json.loads(run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", video]).stdout)
    v = next(s for s in j["streams"] if s["codec_type"] == "video"); a = next((s for s in j["streams"] if s["codec_type"] == "audio"), None)
    fr = v.get("avg_frame_rate") or v.get("r_frame_rate") or "30/1"
    try: n, d = fr.split("/"); fps = float(n) / float(d)
    except Exception: fps = 0.0
    if not (1 <= fps <= 240): fr, fps = "30/1", 30.0
    png = run(["ffmpeg", "-v", "error", "-i", video, "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"]).stdout
    im = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR); H, W = im.shape[:2]      # 自动旋转后的真实尺寸
    dur = float(j["format"].get("duration") or v.get("duration") or 0)
    return dict(W=W, H=H, fps=fps, fr=fr, dur=dur, codec=v.get("codec_name"), pix_fmt=v.get("pix_fmt"), has_audio=a is not None,
                audio=(dict(codec=a.get("codec_name"), sr=a.get("sample_rate"), ch=a.get("channels")) if a else None),
                bitrate=int(j["format"].get("bit_rate") or 0), size_mb=round(int(j["format"].get("size") or 0) / 1e6, 1))

def even(x): return int(round(x / 2) * 2)
def ref_size(W, H, cap=1920): k = min(1.0, cap / max(W, H)); return even(W * k), even(H * k)           # 报告坐标系
def ana_size(W, H, L=480): k = L / max(W, H); return even(W * k), even(H * k)                          # 运动分析分辨率

# ======================================================================== 第一遍:逐帧相机/图层运动 + 运动补偿后的局部帧差
def fit_layers(a, b, aw, ah, layers=3, thr=0.6, minpts=10):
    """顺序 RANSAC 分层。每层:RANSAC(含旋转)选内点 → 内点上做 无旋转 的 (缩放+平移) 最小二乘重估;旋转只作诊断。
    返回 [(scale, theta, tx, ty, n_inliers, spread)],spread=内点 5–95 分位包围盒占画面面积比(区分"全局运镜"与"局部物体")。"""
    out = []
    for _ in range(layers):
        if len(a) < minpts: break
        M, m = cv2.estimateAffinePartial2D(a, b, method=cv2.RANSAC, ransacReprojThreshold=thr, maxIters=600, confidence=0.995)
        if M is None: break
        m = m[:, 0].astype(bool); n = int(m.sum()); P, Q = a[m].astype(np.float64), b[m].astype(np.float64)
        Pc, Qc = P - P.mean(0), Q - Q.mean(0); den = float((Pc ** 2).sum())
        s = float((Pc * Qc).sum() / den) if (n >= 3 and den > 1e-9) else math.hypot(M[0, 0], M[1, 0]); t = Q.mean(0) - s * P.mean(0)
        spread = 0.0
        if n >= 4:
            lo, hi = np.percentile(P, [5, 95], axis=0); spread = float(max(hi[0] - lo[0], 0) * max(hi[1] - lo[1], 0) / (aw * ah))
        out.append((s, math.atan2(M[1, 0], M[0, 0]), float(t[0]), float(t[1]), n, spread)); a, b = a[~m], b[~m]
    return out

def rank_layers(row, aw, minn=8):
    """row=(3,5)[slog,theta,tx,ty,n];返回按速度降序的 [(速度, 层号)](仅内点>=minn)。"""
    out = []
    for l in range(row.shape[0]):
        if not (row[l, 4] >= minn): continue
        out.append((math.hypot(float(row[l, 2]), float(row[l, 3])) + abs(float(row[l, 0])) * aw / 2, l))
    out.sort(reverse=True); return out

def pass1(video, info, aw, ah, gx, gy):
    fsz = aw * ah * 3
    cmd = ["ffmpeg", "-v", "error", "-i", video, "-an", "-vf", f"fps={info['fr']},scale={aw}:{ah}:flags=area", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    pr = subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=fsz * 8)
    ctr = np.array([aw / 2, ah / 2], np.float32)
    lk = dict(winSize=(21, 21), maxLevel=4, criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01))
    rec, E, luma, thumbs, tidx = [], [], [], [], []; step = max(1, int(round(info["fps"] / 2))); prev = prevb = None; i = 0; thw = 160; thh = even(thw * ah / aw)
    while True:
        buf = pr.stdout.read(fsz)
        if len(buf) < fsz: break
        bgr = np.frombuffer(buf, np.uint8).reshape(ah, aw, 3)
        g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY); gb = cv2.GaussianBlur(g, (3, 3), 0); luma.append(float(g.mean()))      # 跟踪用原始灰度(模糊会让角点变钝、位移偏差变大);帧差用轻微模糊的图降噪
        if i % step == 0: thumbs.append(cv2.resize(bgr, (thw, thh), interpolation=cv2.INTER_AREA)); tidx.append(i)
        if prev is not None:
            row = np.full((3, 8), np.nan, np.float32); row[:, 4] = 0; Ms = []; tex = 0.0
            p0 = cv2.goodFeaturesToTrack(prev, 900, 0.004, 5, blockSize=5)
            if p0 is not None and len(p0) >= 12:
                p1, st, _ = cv2.calcOpticalFlowPyrLK(prev, g, p0, None, **lk)
                pb, sb, _ = cv2.calcOpticalFlowPyrLK(g, prev, p1, None, **lk)
                ok = (st[:, 0] == 1) & (sb[:, 0] == 1) & (np.linalg.norm((pb - p0)[:, 0], axis=1) < 0.6)
                if ok.sum() >= 10:
                    lo, hi = np.percentile(p0[ok, 0], [5, 95], axis=0); tex = float((hi[0] - lo[0]) * (hi[1] - lo[1]) / (aw * ah))
                for l, (s, th, tx, ty, n, spr) in enumerate(fit_layers(p0[ok, 0] - ctr, p1[ok, 0] - ctr, aw, ah)):
                    row[l] = (math.log(max(s, 1e-6)), th, tx, ty, n, spr, int(ok.sum()), tex); Ms.append(np.array([[s, 0, tx], [0, s, ty]], np.float64))
            dmin = cv2.absdiff(gb, prevb)                     # 只有"原始帧差、前景补偿后、视差层补偿后"三者都变了的像素,才算真的在局部动
            for _, l in rank_layers(row, aw)[:2]:
                M = Ms[l]; A = M[:, :2]; t = M[:, 2] + ctr - A @ ctr
                w = cv2.warpAffine(prevb, np.hstack([A, t[:, None]]).astype(np.float32), (aw, ah), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
                dmin = np.minimum(dmin, cv2.absdiff(gb, w))
            E.append(cv2.resize(dmin.astype(np.float32), (gx, gy), interpolation=cv2.INTER_AREA)); rec.append(row)
        prev, prevb = g, gb; i += 1
        if i % 600 == 0: LOG("  pass1", i, "frames")
    pr.wait(); LOG("pass1 done:", i, "frames")
    return np.array(rec), np.array(E), np.array(luma), np.array(thumbs), np.array(tidx)

def camera_series(rec, aw, S, RW):
    N = len(rec); lay = np.full((N, 3, 4), np.nan, np.float32); spd = np.full((N, 3), np.nan, np.float32); cov = np.zeros(N, np.float32); spr = np.zeros(N, np.float32)
    tex = np.nan_to_num(rec[:, 0, 7]).astype(np.float32)
    for j in range(N):
        for k, (_, l) in enumerate(rank_layers(rec[j], aw)[:3]):
            slog, th, tx, ty, n, sp_, nt = [float(x) for x in rec[j, l][:7]]; lay[j, k] = (tx * S, ty * S, slog, th); spd[j, k] = math.hypot(tx * S, ty * S) + abs(slog) * RW / 2
            if k == 0: cov[j] = n / max(nt, 1.0); spr[j] = sp_
    return lay, spd, cov, spr, tex

def segment(v, fps, thr_on, min_s=0.10, gap_s=0.12, tail=0.05):
    idx = np.where(v > thr_on)[0]
    if len(idx) == 0: return []
    gap = max(1, int(round(gap_s * fps))); segs = []; a = last = idx[0]
    for k in idx[1:]:
        if k - last > gap: segs.append((a, last)); a = k
        last = k
    segs.append((a, last)); out = []; N = len(v)
    for a, b in segs:
        lo = max(thr_on * 0.1, tail * v[a:b + 1].max())
        while a > 0 and v[a - 1] > lo: a -= 1
        while b < N - 1 and v[b + 1] > lo: b += 1
        out.append([a, b + 1])
    out.sort(); mg = [out[0]]
    for a, b in out[1:]:
        if a <= mg[-1][1]: mg[-1][1] = max(mg[-1][1], b)
        else: mg.append([a, b])
    return [(a, b) for a, b in mg if b - a >= max(3, int(round(min_s * fps)))]

PRESETS = {"linear": (0, 0, 1, 1), "ease": (.25, .1, .25, 1), "ease-in": (.42, 0, 1, 1), "ease-out": (0, 0, .58, 1), "ease-in-out": (.42, 0, .58, 1),
           "easeOutSine": (.61, 1, .88, 1), "easeOutQuad": (.25, .46, .45, .94), "easeOutCubic": (.215, .61, .355, 1), "easeOutQuart": (.165, .84, .44, 1),
           "easeOutQuint": (.23, 1, .32, 1), "easeOutExpo": (.19, 1, .22, 1), "easeOutBack": (.175, .885, .32, 1.275), "easeInOutSine": (.445, .05, .55, .95),
           "easeInOutQuad": (.455, .03, .515, .955), "easeInOutCubic": (.645, .045, .355, 1), "easeInOutQuart": (.77, 0, .175, 1), "easeInOutExpo": (1, 0, 0, 1),
           "easeInCubic": (.55, .055, .675, .19), "easeInQuart": (.895, .03, .685, .22)}
_S401 = np.linspace(0, 1, 401)
def bez_y(x1, y1, x2, y2, u):
    s = _S401; X = 3 * (1 - s) ** 2 * s * x1 + 3 * (1 - s) * s ** 2 * x2 + s ** 3; Y = 3 * (1 - s) ** 2 * s * y1 + 3 * (1 - s) * s ** 2 * y2 + s ** 3
    return np.interp(u, X, Y)

def fit_bezier(u, p):
    """对 (x1,x2) 网格搜索;给定 (x1,x2) 时 (y1,y2) 有闭式最小二乘解。返回 (rmse,(x1,y1,x2,y2))。"""
    def solve(x1, x2):
        s = _S401; X = 3 * (1 - s) ** 2 * s * x1 + 3 * (1 - s) * s ** 2 * x2 + s ** 3; ss = np.interp(u, X, s)
        a = 3 * (1 - ss) ** 2 * ss; b = 3 * (1 - ss) * ss ** 2; c = ss ** 3
        sol = np.linalg.lstsq(np.stack([a, b], 1), p - c, rcond=None)[0]; y1, y2 = np.clip(sol, -1.0, 2.0)
        return float(np.sqrt(np.mean((a * y1 + b * y2 + c - p) ** 2))), (x1, float(y1), x2, float(y2))
    best = (9.0, None)
    for x1 in np.linspace(0, 1, 26):
        for x2 in np.linspace(0, 1, 26):
            r = solve(x1, x2)
            if r[0] < best[0]: best = r
    bx1, _, bx2, _ = best[1]
    for x1 in np.clip(np.linspace(bx1 - .04, bx1 + .04, 9), 0, 1):
        for x2 in np.clip(np.linspace(bx2 - .04, bx2 + .04, 9), 0, 1):
            r = solve(x1, x2)
            if r[0] < best[0]: best = r
    return best

SPREAD_GLOBAL = 0.45      # 没有视差/静态背景层可参照时:前景内点包围盒占画面面积 ≥ 此值 → 整屏运动
MAX_MOVE_S, ZOOM_SANE = 6.0, (0.15, 6.5)   # 合理性护栏
R2_GLOBAL = (0.08, 0.97)  # 有第二层(视差背景)时:它的速度/前景速度 落在此区间 → 背景也在跟着动 → 全局运镜;≈0 表示背景纹丝不动 → 只是局部物体在动

def describe_moves(segs, lay, spd, cov, spr, fps, RW, thr_on):
    moves = []; U = np.linspace(0, 1, 25)
    for (a, b) in segs:
        n = b - a; L0 = np.nan_to_num(lay[a:b, 0]); v = np.nan_to_num(spd[a:b, 0]); vs = np.convolve(v, np.ones(3) / 3, mode="same")
        if vs.max() < thr_on: continue
        dx, dy, dz, dth = [float(L0[:, k].sum()) for k in range(4)]; pathz = float(np.abs(L0[:, 2]).sum()); path = float(v.sum())
        if path <= 0: continue
        c0 = np.r_[0, np.cumsum(v) / path]; prog = np.interp(U, np.arange(n + 1) / n, c0); pk = int(np.argmax(vs)); err, bz = fit_bezier(U, prog)
        pre = min(((float(np.sqrt(np.mean((bez_y(*q, U) - prog) ** 2))), nm) for nm, q in PRESETS.items()))
        r2 = spd[a:b, 1] / np.maximum(spd[a:b, 0], 1e-6); r3 = spd[a:b, 2] / np.maximum(spd[a:b, 0], 1e-6)
        core = vs > 0.3 * vs.max(); sp_ = float(np.median(spr[a:b][core])); cv_ = float(np.median(cov[a:b][core]))
        l2 = float(np.nanmedian(r2)) if np.isfinite(r2).sum() >= 3 else None; l3 = float(np.nanmedian(r3)) if np.isfinite(r3).sum() >= 3 else None
        scope = "全局" if ((l2 is not None and R2_GLOBAL[0] <= l2 <= R2_GLOBAL[1]) or sp_ >= SPREAD_GLOBAL) else "局部"
        zf = math.exp(dz)
        if n / fps > MAX_MOVE_S or not (ZOOM_SANE[0] <= zf <= ZOOM_SANE[1]): scope = "不可信"      # 持续太久/缩放离谱 → 多半是粒子、形变等非刚体运动被硬拟合成了相似变换
        kind = []
        if math.hypot(dx, dy) > 0.02 * RW: kind.append("平移")
        if abs(dz) > 0.03: kind.append("推近" if dz > 0 else "拉远")
        if pathz > 1.5 * abs(dz) + 0.08: kind.append("缩放往返")
        moves.append(dict(i0=a, i1=b, t0=a / fps, t1=b / fps, dur=n / fps, content_dx=dx, content_dy=dy, cam_dx=-dx, cam_dy=-dy, zoom_factor=zf, rot_deg_diag=math.degrees(dth),
                          path_px=path, peak_px_s=float(vs.max() * fps), peak_frac=(pk + 0.5) / n, t50_frac=float(np.interp(0.5, prog, U)),
                          bezier=[round(float(x), 3) for x in bz], bezier_rmse=round(err, 4), preset=pre[1], preset_rmse=round(pre[0], 4), progress=[round(float(x), 3) for x in prog[::2]],
                          kind=" + ".join(kind) if kind else "微动", spread=sp_, coverage=cv_, scope=scope, layer2_ratio=l2, layer3_ratio=l3))
    return moves

def drifts(v, fps, RW, moves):
    """慢速推拉/漂移:速度在 噪声~运动阈值 之间并持续>=1s,且不在 moves 内。"""
    lo, hi = 0.004 * RW / fps, 0.04 * RW / fps; vs = np.convolve(np.nan_to_num(v), np.ones(int(fps // 2) | 1) / (int(fps // 2) | 1), mode="same")
    mask = (vs > lo) & (vs <= hi * 1.2)
    for m in moves: mask[m["i0"]:m["i1"]] = False
    out = []; i = 0; N = len(mask)
    while i < N:
        if mask[i]:
            j = i
            while j < N and mask[j]: j += 1
            if (j - i) / fps >= 1.0: out.append((i, j))
            i = j
        else: i += 1
    return out

# ======================================================================== 元素动效事件
def trend(t, y):
    t = np.asarray(t, float); y = np.asarray(y, float)
    if len(t) < 3 or np.ptp(t) == 0 or np.ptp(y) == 0: return 0.0, 0.0
    sl = np.polyfit(t, y, 1)[0]; r = np.corrcoef(t, y)[0, 1]; return float(sl), float(r)

def local_events(E, fps, RW, RH, suppress, thr=None):
    """suppress: 布尔数组,全局运镜的帧(这些帧里局部变化不可分,屏蔽掉,由 moves 表负责)。"""
    N, gy, gx = E.shape; Ew = E.copy(); Ew[suppress] = 0; quiet = Ew[~suppress] if (~suppress).sum() > 10 else Ew
    noise = float(np.percentile(quiet, 50)); thr = max(0.5, 3.0 * noise) if thr is None else thr
    A = Ew > thr; B = A.copy(); g = max(1, int(round(0.08 * fps)))
    for k in range(1, g + 1): B[k:] |= A[:-k]; B[:-k] |= A[k:]
    parent = []
    def find(x):
        while parent[x] != x: parent[x] = parent[parent[x]]; x = parent[x]
        return x
    labs = []; prev = None
    for i in range(N):
        n, lab = cv2.connectedComponents(B[i].astype(np.uint8), connectivity=8); base = len(parent); parent.extend(range(base, base + n - 1))
        if prev is not None and n > 1:
            pl, pb = prev; both = (lab > 0) & (pl > 0)
            for l, q in set(zip(lab[both].tolist(), pl[both].tolist())):
                ra, rb = find(base + l - 1), find(pb + q - 1)
                if ra != rb: parent[rb] = ra
        labs.append((lab, base)); prev = (lab, base)
    ev = {}; cw, ch = RW / gx, RH / gy
    for i in range(N):
        lab, base = labs[i]
        for l in range(1, int(lab.max()) + 1):
            m = (lab == l) & A[i]
            if not m.any(): continue
            ys, xs = np.where(m); en = float(E[i][m].sum()); d = ev.setdefault(find(base + l - 1), dict(f=[], cx=[], cy=[], x0=[], x1=[], y0=[], y1=[], en=[], na=[]))
            d["f"].append(i); d["cx"].append(xs.mean()); d["cy"].append(ys.mean()); d["x0"].append(xs.min()); d["x1"].append(xs.max() + 1); d["y0"].append(ys.min()); d["y1"].append(ys.max() + 1); d["en"].append(en); d["na"].append(len(xs))
    out = []
    for d in ev.values():
        f = np.array(d["f"]); t0, t1 = int(f.min()), int(f.max()) + 1; dur = (t1 - t0) / fps
        if dur < max(0.05, 3 / fps): continue
        score = float(np.sum(d["en"]) / fps); x0, x1, y0, y1 = min(d["x0"]), max(d["x1"]), min(d["y0"]), max(d["y1"])
        if (x1 - x0) * (y1 - y0) < 2 and dur < 0.12: continue                 # 单格 + 极短 = 闪烁/噪点
        out.append(dict(i0=t0, i1=t1, t0=t0 / fps, t1=t1 / fps, dur=dur, bbox=[int(x0 * cw), int(y0 * ch), int(x1 * cw), int(y1 * ch)], area_frac=float((x1 - x0) * (y1 - y0) / (gx * gy)),
                        score=score, peak=float(np.max(d["en"])), d=d))
    # 把"全屏变化"单独标出(转场/整体淡入淡出/闪白);其余按类型猜测
    for e in out:
        d = e["d"]; t = np.array(d["f"]) / fps; dur = e["dur"]; sx, rx = trend(t, d["x1"]); sl, rl = trend(t, d["x0"]); sy, ry = trend(t, d["y1"]); syt, ryt = trend(t, d["y0"])
        scx, rcx = trend(t, d["cx"]); scy, rcy = trend(t, d["cy"]); wx = max(d["x1"]) - min(d["x0"]); wy = max(d["y1"]) - min(d["y0"])
        dR, dL, dB, dT, dCx, dCy = sx * dur, sl * dur, sy * dur, syt * dur, scx * dur, scy * dur
        guess = "渐变/淡入淡出/虚化聚焦(范围稳定)"
        if e["area_frac"] > 0.6: guess = "全屏变化(转场/整体淡入淡出/闪白)"
        elif dur < 0.3: guess = "瞬时闪现/弹出/闪动"
        if e["area_frac"] <= 0.6:
            if dR >= 3 and rx > 0.8 and abs(dL) < 2: guess = "自左向右逐步揭示(打字机/擦除/进度)"
            elif dL <= -3 and rl < -0.8 and abs(dR) < 2: guess = "自右向左逐步揭示"
            elif dB >= 2 and ry > 0.8 and abs(dT) < 1.5: guess = "自上而下逐步揭示/下落"
            elif dT <= -2 and ryt < -0.8 and abs(dB) < 1.5: guess = "自下而上逐步揭示"
            elif abs(dCx) >= 3 and abs(rcx) > 0.85 and wx < 14: guess = "整体横向位移(滑入/滑出/光标移动)" + ("→" if dCx > 0 else "←")
            elif abs(dCy) >= 2 and abs(rcy) > 0.85: guess = "整体纵向位移" + ("↓" if dCy > 0 else "↑")
        e["guess"] = guess; e["extent_cells"] = [int(wx), int(wy)]; del e["d"]
    out.sort(key=lambda e: e["t0"]); return out, thr

# ======================================================================== 切点
def detect_cuts(video):
    try:
        from scenedetect import detect, ContentDetector, ThresholdDetector
    except Exception as ex: return None, "scenedetect 不可用: %s" % ex
    cuts = [round(s[0].seconds, 3) for s in detect(video, ContentDetector(threshold=27.0, min_scene_len=8), show_progress=False)][1:]
    fades = [round(s[0].seconds, 3) for s in detect(video, ThresholdDetector(threshold=12, min_scene_len=8), show_progress=False)][1:]
    return dict(hard_cuts=cuts, fade_points=fades), None

# ======================================================================== 配色
def palette(thumbs, k=6):
    px = thumbs.reshape(-1, 3); px = px[::max(1, len(px) // 60000)]
    lab = cv2.cvtColor(px.reshape(-1, 1, 3).astype(np.float32) / 255.0, cv2.COLOR_BGR2Lab).reshape(-1, 3).astype(np.float32)
    _, labels, cent = cv2.kmeans(lab, k, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5), 3, cv2.KMEANS_PP_CENTERS)
    w = np.bincount(labels[:, 0], minlength=k) / len(labels); bgr = cv2.cvtColor(cent.reshape(-1, 1, 3).astype(np.float32), cv2.COLOR_Lab2BGR).reshape(-1, 3) * 255
    return [dict(hex=hexc(bgr[j]), pct=round(float(w[j]) * 100, 1), L=round(float(cent[j, 0]), 1), chroma=round(float(np.hypot(cent[j, 1], cent[j, 2])), 1)) for j in np.argsort(-w)]

def color_stats(thumbs, tidx, fps):
    hsv = np.array([cv2.cvtColor(t, cv2.COLOR_BGR2HSV) for t in thumbs]).astype(np.float32)
    return dict(mean_luma=float(np.mean([t.mean() for t in thumbs])), mean_sat=float(hsv[..., 1].mean() / 255), sat_p90=float(np.percentile(hsv[..., 1], 90) / 255),
                contrast=float(np.mean([cv2.cvtColor(t, cv2.COLOR_BGR2GRAY).std() for t in thumbs])))

# ======================================================================== 音频
def audio_analysis(video):
    raw = run(["ffmpeg", "-v", "error", "-i", video, "-vn", "-ac", "1", "-ar", "22050", "-f", "f32le", "-"]).stdout; sr = 22050; x = np.frombuffer(raw, np.float32)
    if len(x) < sr: return None
    n_fft, hop = 1024, 256; win = np.hanning(n_fft).astype(np.float32); nfr = 1 + (len(x) - n_fft) // hop
    L = np.zeros((nfr, n_fft // 2 + 1), np.float32)
    for s in range(0, nfr, 2000):
        e = min(nfr, s + 2000); idx = np.arange(n_fft)[None, :] + hop * np.arange(s, e)[:, None]; L[s:e] = np.log1p(np.abs(np.fft.rfft(x[idx] * win, axis=1)) * 20)
    flux = np.r_[0, np.maximum(L[1:] - L[:-1], 0).sum(1)]; flux = flux / (np.percentile(flux, 95) + 1e-9); fr = sr / hop
    w = max(3, int(fr * 0.5)); pad = np.pad(flux, w, mode="edge"); win_v = np.lib.stride_tricks.sliding_window_view(pad, 2 * w + 1)[:len(flux)]
    med = np.median(win_v, axis=1); thr = med + 0.35; peaks = []
    for i in range(1, len(flux) - 1):
        if flux[i] > thr[i] and flux[i] >= flux[i - 1] and flux[i] > flux[i + 1]:
            if peaks and (i - peaks[-1]) / fr < 0.06:
                if flux[i] > flux[peaks[-1]]: peaks[-1] = i
            else: peaks.append(i)
    onsets = [dict(t=round(p / fr + n_fft / 2 / sr, 3), strength=round(float(flux[p]), 2)) for p in peaks]      # 窗口中心时间
    # 100ms 包络(dBFS)
    seg = int(sr * 0.1); n = len(x) // seg; rms = np.sqrt((x[:n * seg].reshape(n, seg) ** 2).mean(1) + 1e-12); db = 20 * np.log10(rms + 1e-9)
    # 节拍估计:对 onset 强度做自相关
    env = flux - flux.mean(); ac = np.correlate(env, env, "full")[len(env) - 1:]; lo, hi = int(fr * 60 / 200), int(fr * 60 / 60); bpm = None
    if hi < len(ac) and ac[0] > 0:
        k = lo + int(np.argmax(ac[lo:hi]))
        if ac[k] / ac[0] > 0.12:
            cands = [(c, ac[c]) for c in {k, k // 2, k * 2, int(round(k / 1.5)), int(round(k * 1.5))} if lo <= c < hi and c < len(ac)]
            top = max(a for _, a in cands); good = [c for c, a in cands if a >= 0.75 * top]
            best = min(good, key=lambda c: abs(math.log((60 * fr / c) / 120.0)))                                  # 八度歧义:在强度接近的候选里取最接近 120BPM 的
            bpm = round(60 * fr / best, 1)
    loud = {}
    try:
        err = subprocess.run(["ffmpeg", "-hide_banner", "-i", video, "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
        tail = err[err.rfind("Summary:"):]
        for key, tag in (("lufs", "I:"), ("lra", "LRA:"), ("peak_db", "Peak:")):
            p = tail.find(tag)
            if p >= 0: loud[key] = float(tail[p + len(tag):].split()[0])
    except Exception: pass
    return dict(onsets=onsets, rms_db=[round(float(v), 1) for v in db], bpm=bpm, loudness=loud, duration=len(x) / sr)

# ======================================================================== OCR(多进程、近重复帧复用)
def _ocr_init():
    """每个 worker 建一个单线程 OCR 引擎(多进程各自单线程,比一个多线程引擎快)。
    兼容 rapidocr_onnxruntime 新旧两版:新版可直接传线程数,旧版靠替换 utils.SessionOptions。"""
    from rapidocr_onnxruntime import RapidOCR
    global _ENG
    try:
        _ENG = RapidOCR(intra_op_num_threads=1, inter_op_num_threads=1)
        return
    except Exception:
        pass
    try:
        import rapidocr_onnxruntime.utils as ru
        _orig = getattr(ru, "SessionOptions", None)
        if _orig is not None:
            def _so(): s = _orig(); s.intra_op_num_threads = 1; s.inter_op_num_threads = 1; return s
            ru.SessionOptions = _so
    except Exception:
        pass
    _ENG = RapidOCR()

def _ocr_one(path):
    im = cv2.imread(path); res, _ = _ENG(im, text_score=0.45); out = []
    for box, txt, sc in (res or []):
        xs = [p[0] for p in box]; ys = [p[1] for p in box]; out.append((str(txt), float(sc), float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys))))
    return out

def ocr_stage(video, info, rw, rh, outdir, fps_ocr, workers, skip_fn):
    d = os.path.join(outdir, "_ocr"); shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    run(["ffmpeg", "-v", "error", "-y", "-i", video, "-an", "-vf", f"fps={fps_ocr},scale={rw}:{rh}:flags=lanczos", "-q:v", "2", os.path.join(d, "%05d.jpg")])
    files = sorted(os.path.join(d, f) for f in os.listdir(d)); small = [cv2.resize(cv2.imread(f, cv2.IMREAD_GRAYSCALE), (128, int(128 * rh / rw))).astype(np.float32) for f in files]
    skip = [bool(skip_fn(k / fps_ocr)) for k in range(len(files))]       # 镜头重度运动模糊的帧:不识别(只会产出乱码,真正的文字特效交给事件条带看)
    todo = []; src = []; last = None                                      # last = 最近一次真正送去识别的帧;与它几乎一样的帧直接复用结果
    for k, s in enumerate(small):
        if skip[k]: src.append(None)
        elif last is not None and float(np.abs(s - small[last]).mean()) < 1.0: src.append(src[last])
        else: src.append(len(todo)); todo.append(files[k]); last = k
    LOG("OCR:", len(files), "frames sampled,", sum(skip), "skipped (camera blur),", len(todo), "unique ->", workers, "workers")
    from multiprocessing import Pool
    with Pool(workers, initializer=_ocr_init) as pool: res = pool.map(_ocr_one, todo, chunksize=2)
    samples = [(k / fps_ocr, ([] if src[k] is None else res[src[k]]), src[k] is None) for k in range(len(files))]
    return samples, d, files

import re
def norm(s): return "".join(s.split()).lower()
def shape(s): return re.sub(r"\d+", "#", s)
def tsim(a, b):
    if a == b: return 1.0
    if not a or not b: return 0.0
    if re.search(r"\d", a) and re.search(r"\d", b) and shape(a) == shape(b): return 0.95
    if a.startswith(b) or b.startswith(a): return 0.9
    if a in b or b in a: return 0.75
    return difflib.SequenceMatcher(None, a, b).ratio()

def build_tracks(samples, fps_ocr, RW, RH, move_mask_fn):
    tracks = []; active = []
    for t, dets, skipped in samples:
        if skipped: continue
        used = set(); moving = move_mask_fn(t)
        for tx, sc, x0, y0, x1, y1 in sorted(dets, key=lambda d: -d[1] * len(d[0])):
            n = norm(tx)
            if not n: continue
            best = None; bs = 0
            for tr in active:
                if id(tr) in used: continue
                s = tsim(norm(tr["text"]), n)
                if s < 0.7: continue
                bx = tr["boxes"][-1]; cx, cy = (x0 + x1) / 2, (y0 + y1) / 2; bcx, bcy = (bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2; h = max(y1 - y0, bx[3] - bx[1])
                same_line = abs((y0 + y1) / 2 - bcy) < 0.6 * h + 0.01 * RH and (abs(x0 - bx[0]) < 0.03 * RW or abs(cx - bcx) < 0.04 * RW)
                if not (moving or same_line): continue
                dist = math.hypot(cx - bcx, cy - bcy)
                if moving and dist > 0.95 * RW: continue
                score = s - dist / (2 * RW)
                if score > bs: bs, best = score, tr
            if best is None:
                best = dict(text=tx, t_first=t, t_last=t, boxes=[], confs=[], strings=[(t, tx)], miss=0); tracks.append(best); active.append(best)
            else:
                if tx != best["strings"][-1][1]: best["strings"].append((t, tx))
            if len(norm(tx)) >= len(norm(best["text"])): best["text"] = tx
            best["t_last"] = t; best["boxes"].append((x0, y0, x1, y1)); best["confs"].append(sc); best["miss"] = 0; used.add(id(best))
        for a in active:
            if id(a) not in used: a["miss"] += 1
        active = [a for a in active if a["miss"] <= 1]
    out = []
    for k, tr in enumerate(tracks):
        b = np.array(tr["boxes"]); med = np.median(b, axis=0); st = tr["strings"]; grows = sum(1 for i in range(1, len(st)) if norm(st[i][1]).startswith(norm(st[i - 1][1])) and len(norm(st[i][1])) > len(norm(st[i - 1][1])))
        typed = grows >= 2 and len(st) >= 3 and len(norm(st[-1][1])) - len(norm(st[0][1])) >= 3; cps = None
        if typed:
            dt = st[-1][0] - st[0][0]; cps = (len(norm(st[-1][1])) - len(norm(st[0][1]))) / dt if dt > 0 else None
            if cps is not None and cps <= 0: typed, cps = False, None
        out.append(dict(id=k + 1, text=tr["text"], t_first=tr["t_first"], t_last=tr["t_last"] + 1.0 / fps_ocr, n=len(b), conf=float(np.mean(tr["confs"])), bbox=[float(x) for x in med],
                        height=float(med[3] - med[1]), typed=typed, chars_per_s=(round(cps, 1) if cps else None), strings=[(round(a, 2), s) for a, s in st][:12]))
    return [t for t in out if t["n"] >= 2 or t["conf"] >= 0.85]

def text_colors(tracks, files, fps_ocr):
    """底色=文字框外一圈像素的中位数;字色=框内离底色最远(Lab)的 15% 像素的均值。对比度太低(<10)则标注 low-contrast。"""
    for tr in tracks:
        try:
            k = min(len(files) - 1, int(round((tr["t_first"] + tr["t_last"] - 1.0 / fps_ocr) / 2 * fps_ocr))); im = cv2.imread(files[k]); H, W = im.shape[:2]
            x0, y0, x1, y1 = [int(v) for v in tr["bbox"]]; m = 10; X0, Y0, X1, Y1 = max(0, x0 - m), max(0, y0 - m), min(W, x1 + m), min(H, y1 + m)
            crop = im[Y0:Y1, X0:X1]
            if crop.size < 300: continue
            inner = np.zeros(crop.shape[:2], bool); inner[max(0, y0 - Y0 - 2):y1 - Y0 + 2, max(0, x0 - X0 - 2):x1 - X0 + 2] = True
            lab = cv2.cvtColor(crop.astype(np.float32) / 255.0, cv2.COLOR_BGR2Lab); ring = lab[~inner]
            if len(ring) < 20: continue
            bg = np.median(ring, axis=0); dist = np.linalg.norm(lab[inner] - bg, axis=1); sel = dist >= np.percentile(dist, 85)
            fg_lab = lab[inner][sel].mean(0); bgr = crop[inner]; fg = bgr[sel].mean(0); bgc = np.median(crop[~inner], axis=0)
            tr["color"] = hexc(fg); tr["bg"] = hexc(bgc); tr["contrast"] = round(float(np.linalg.norm(fg_lab - bg)), 1)
            if tr["contrast"] < 10: tr["color"] += "(low-contrast)"
        except Exception: pass
    return tracks

# ======================================================================== 第二遍:取帧(总览/条带)
def grab_frames(video, info, rw, rh, needs, tmpdir):
    """needs: {frame_idx: [(key, box|None)]} -> {key: BGR}. 一次 ffmpeg select 取全部需要的帧。"""
    if not needs: return {}
    idxs = sorted(needs); want = set(idxs); last = idxs[-1]
    # 逐帧流式解码、只留需要的帧:select 表达式在长视频里会超长导致 ffmpeg 报错
    graph = f"fps={info['fr']},scale={rw}:{rh}:flags=lanczos"
    pr = subprocess.Popen(["ffmpeg", "-v", "error", "-i", video, "-an", "-vf", graph, "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE, bufsize=rw * rh * 3 * 4)
    got = {}; fsz = rw * rh * 3
    for i in range(last + 1):
        buf = pr.stdout.read(fsz)
        if len(buf) < fsz: break
        if i not in want: continue
        im = np.frombuffer(buf, np.uint8).reshape(rh, rw, 3)
        for key, box in needs[i]: got[key] = im.copy() if box is None else im[box[1]:box[3], box[0]:box[2]].copy()
    pr.kill()
    pr.stdout.close(); pr.wait(); return got

def stamp(img, text, pos=(6, 4), sz=18):
    pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)); d = ImageDraw.Draw(pil); f = font(sz); bb = d.textbbox(pos, text, font=f)
    d.rectangle((bb[0] - 4, bb[1] - 2, bb[2] + 4, bb[3] + 3), fill=(0, 0, 0)); d.text(pos, text, font=f, fill=(255, 255, 255)); return cv2.cvtColor(np.asarray(pil), cv2.COLOR_RGB2BGR)

def grid(items, cols, cw, header=None, ch=None):
    ims = []
    for img, cap in items:
        h = int(round(img.shape[0] * cw / img.shape[1])) if ch is None else ch; c = cv2.resize(img, (cw, h), interpolation=cv2.INTER_AREA); ims.append(stamp(c, cap) if cap else c)
    h = max(i.shape[0] for i in ims); rows = []
    for r in range(0, len(ims), cols):
        row = ims[r:r + cols]; row = [np.pad(i, ((0, h - i.shape[0]), (2, 2), (0, 0)), constant_values=18) for i in row]; row += [np.full((h, cw + 4, 3), 18, np.uint8)] * (cols - len(row)); rows.append(np.hstack(row))
    g = np.vstack([np.pad(r, ((2, 2), (0, 0), (0, 0)), constant_values=18) for r in rows])
    if header: g = np.vstack([stamp(np.full((34, g.shape[1], 3), 30, np.uint8), header, (8, 5), 20), g])
    return g

# ======================================================================== 合并时间线图
def timeline_png(path, dur, fps, spd0, moves, events, tracks, audio, W=1920):
    left, right = 150, 20; tw = W - left - right; X = lambda t: int(left + t / dur * tw)
    tracks = sorted(sorted(tracks, key=lambda t: -(t["height"] * (t["t_last"] - t["t_first"])))[:70], key=lambda t: t["t_first"])
    rows_e = pack([(e["t0"], e["t1"]) for e in events], 0.04); rows_t = pack([(t["t_first"], t["t_last"]) for t in tracks], 0.05)
    H = 40 + 130 + 40 + max(1, max(rows_e, default=0) + 1) * 13 + 30 + max(1, max(rows_t, default=0) + 1) * 15 + 30 + 100
    im = Image.new("RGB", (W, H), (16, 18, 22)); d = ImageDraw.Draw(im); f = font(13); f2 = font(11); y = 12
    for s in range(int(dur) + 1):
        x = X(s); d.line((x, 30, x, H - 4), fill=(32, 36, 44) if s % 5 else (52, 58, 70))
        if s % (1 if dur <= 45 else 5) == 0: d.text((x + 2, 12), "%ds" % s, font=f2, fill=(150, 156, 170))
    y = 40; d.text((8, y + 50), "镜头速度", font=f, fill=(190, 196, 210)); d.text((8, y + 70), "(内容位移/s)", font=f2, fill=(120, 126, 140))
    v = np.nan_to_num(spd0) * fps; vmax = max(float(np.percentile(v, 99.5)), 1.0); pts = [(left, y + 120)]
    for i in range(0, len(v), max(1, len(v) // tw)): pts.append((X(i / fps), y + 120 - int(min(1.0, v[i] / vmax) * 110)))
    pts.append((left + tw, y + 120)); d.polygon(pts, fill=(52, 120, 200))
    for k, m in enumerate(moves): d.rectangle((X(m["t0"]), y + 2, max(X(m["t1"]), X(m["t0"]) + 2), y + 12), fill=(235, 160, 60)); d.text((X(m["t0"]) + 1, y + 13), str(k + 1), font=f2, fill=(255, 200, 120))
    y += 140; d.text((8, y), "元素动效", font=f, fill=(190, 196, 210)); col = {"全": (230, 90, 90), "打": (90, 200, 120), "瞬": (230, 200, 80), "渐": (120, 160, 230), "整": (200, 120, 220), "自": (90, 200, 120)}
    for k, e in enumerate(events): d.rectangle((X(e["t0"]), y + rows_e[k] * 13, max(X(e["t1"]), X(e["t0"]) + 3), y + rows_e[k] * 13 + 9), fill=col.get(e["guess"][0], (150, 150, 150)))
    y += max(1, max(rows_e, default=0) + 1) * 13 + 20; d.text((8, y), "屏幕文字", font=f, fill=(190, 196, 210))
    for k, t in enumerate(tracks):
        x0, x1 = X(t["t_first"]), max(X(t["t_last"]), X(t["t_first"]) + 3); yy = y + rows_t[k] * 15; d.rectangle((x0, yy, x1, yy + 12), fill=(60, 70, 90)); d.text((x0 + 2, yy - 1), t["text"][:40], font=f2, fill=(235, 238, 245))
    y += max(1, max(rows_t, default=0) + 1) * 15 + 20; d.text((8, y + 30), "音频", font=f, fill=(190, 196, 210))
    if audio:
        db = np.array(audio["rms_db"]); lo, hi = -60.0, max(float(db.max()), -20.0); pts = [(left, y + 90)]
        for i, vv in enumerate(db): pts.append((X(i * 0.1), y + 90 - int(max(0.0, (vv - lo) / (hi - lo)) * 80)))
        pts.append((left + tw, y + 90)); d.polygon(pts, fill=(70, 150, 110))
        for o in audio["onsets"]:
            if o["strength"] >= 0.6: d.line((X(o["t"]), y + 4, X(o["t"]), y + 18), fill=(255, 220, 120))
    im.save(path)

def pack(spans, gap):
    ends = []; rows = []
    for a, b in spans:
        for r, e in enumerate(ends):
            if a >= e + gap: ends[r] = b; rows.append(r); break
        else: ends.append(b); rows.append(len(ends) - 1)
    return rows

# ======================================================================== 主流程
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("video"); ap.add_argument("out"); ap.add_argument("--ocr-fps", type=float, default=4.0); ap.add_argument("--no-ocr", action="store_true")
    ap.add_argument("--no-cuts", action="store_true"); ap.add_argument("--no-audio", action="store_true"); ap.add_argument("--no-images", action="store_true"); ap.add_argument("--max-events", type=int, default=40)
    ap.add_argument("--sheet-step", type=float, default=0.0, help="总览联系表取帧间隔(秒);0=自动"); args = ap.parse_args()
    out = os.path.abspath(args.out); os.makedirs(out, exist_ok=True)
    for sub in ("sheets", "moves", "events"): shutil.rmtree(os.path.join(out, sub), ignore_errors=True); os.makedirs(os.path.join(out, sub))
    info = probe(args.video); W, H, fps = info["W"], info["H"], info["fps"]; RW, RH = ref_size(W, H); aw, ah = ana_size(W, H); S = RW / aw
    gx = max(8, aw // 20); gy = max(8, ah // 20)                      # 局部变化网格:约 20px(分析分辨率)一格
    LOG("video %dx%d @ %.3f fps, %.2fs, audio=%s | ref %dx%d, analysis %dx%d, grid %dx%d" % (W, H, fps, info["dur"], info["has_audio"], RW, RH, aw, ah, gx, gy))
    rec, E, luma, thumbs, tidx = pass1(args.video, info, aw, ah, gx, gy); N = len(rec); dur = (N + 1) / fps; info["dur_decoded"] = dur
    lay, spd, cov, spr, tex = camera_series(rec, aw, S, RW); np.savez(os.path.join(out, "motion.npz"), rec=rec, lay=lay, spd=spd, cov=cov, spr=spr, tex=tex, E=E, luma=luma, thumbs=thumbs, tidx=tidx)
    v0 = np.nan_to_num(spd[:, 0]); thr_on = 0.04 * RW / fps; tex_med = float(np.median(tex)); LOG("texture coverage (tracked-feature spread, median): %.2f" % tex_med)
    segs = segment(v0, fps, thr_on); moves = describe_moves(segs, lay, spd, cov, spr, fps, RW, thr_on); dr = drifts(spd[:, 0], fps, RW, moves)
    drift_list = [dict(t0=a / fps, t1=b / fps, zoom_factor=math.exp(float(np.nansum(lay[a:b, 0, 2]))), cam_dx=-float(np.nansum(lay[a:b, 0, 0])), cam_dy=-float(np.nansum(lay[a:b, 0, 1]))) for a, b in dr]
    LOG("camera: %d moves, %d slow drifts" % (len(moves), len(drift_list)))
    glob = np.zeros(N, bool)
    for m in moves:
        if m["scope"] == "全局": glob[max(0, m["i0"] - 2):m["i1"] + 2] = True
    events, ethr = local_events(E, fps, RW, RH, glob); LOG("element events: %d (threshold %.2f); %d moves global / %d local" % (len(events), ethr, sum(m["scope"] == "全局" for m in moves), sum(m["scope"] == "局部" for m in moves)))
    cuts, cut_err = (None, "已跳过") if args.no_cuts else detect_cuts(args.video); LOG("cuts:", cuts if cuts is not None else cut_err)
    cs = color_stats(thumbs, tidx, fps); pal = palette(thumbs); wl = max(1, int(round(len(thumbs) / max(1, round(dur / 6.0))))); pal_t = []
    for s in range(0, len(thumbs), wl):
        seg = thumbs[s:s + wl]
        if len(seg) >= 3: pal_t.append(dict(t0=float(tidx[s]) / fps, t1=float(tidx[min(len(tidx) - 1, s + wl - 1)]) / fps, colors=palette(seg, 4)[:4]))
    audio = None if (args.no_audio or not info["has_audio"]) else audio_analysis(args.video); LOG("audio:", "n/a" if not audio else "%d onsets, bpm=%s, %s" % (len(audio["onsets"]), audio["bpm"], audio["loudness"]))
    tracks = []; ocr_dir = None
    if not args.no_ocr:
        try:
            vsm = np.convolve(v0, np.ones(5) / 5, mode="same"); blur_skip = lambda t: bool(vsm[min(len(vsm) - 1, int(t * fps))] > 6 * thr_on)
            samples, ocr_dir, files = ocr_stage(args.video, info, RW, RH, out, args.ocr_fps, min(4, os.cpu_count() or 2), blur_skip)
            moving = lambda t: bool(v0[min(len(v0) - 1, int(t * fps))] > thr_on * 0.5) or bool(v0[min(len(v0) - 1, int((t - 1.0 / args.ocr_fps) * fps))] > thr_on * 0.5)
            tracks = text_colors(build_tracks(samples, args.ocr_fps, RW, RH, moving), files, args.ocr_fps); LOG("text tracks:", len(tracks))
        except Exception as ex: LOG("OCR 失败/跳过:", repr(ex))
        finally:
            if ocr_dir: shutil.rmtree(ocr_dir, ignore_errors=True)
    # ---------------- 图片
    files_idx = {}
    if not args.no_images:
        step = args.sheet_step or max(0.5, round(dur / 48 * 4) / 4); st = np.arange(0, dur - 0.05, step); needs = {}
        for k, t in enumerate(st): needs.setdefault(min(N, int(round(t * fps))), []).append((("sheet", k), None))
        for mi, m in enumerate(moves):
            for q, fi in enumerate(np.linspace(m["i0"], min(N, m["i1"]), 8)): needs.setdefault(int(round(fi)), []).append((("move", mi, q), None))
        ranked = sorted(range(len(events)), key=lambda k: -events[k]["score"] * math.log1p(events[k]["area_frac"] * 100)); sel = sorted(ranked[:args.max_events], key=lambda k: events[k]["t0"])
        for ei in sel:
            e = events[ei]; x0, y0, x1, y1 = e["bbox"]; cx, cy = (x0 + x1) / 2, (y0 + y1) / 2; bw = max(x1 - x0, 0.28 * RW) * 1.25; bw = min(bw, RW); bh = bw * RH / RW
            bx0 = int(max(0, min(RW - bw, cx - bw / 2))); by0 = int(max(0, min(RH - bh, cy - bh / 2))); box = [bx0, by0, int(bx0 + bw), int(by0 + bh)]; e["crop"] = box
            a, b = e["i0"] - int(0.06 * fps), e["i1"] + int(0.10 * fps)
            for q, fi in enumerate(np.linspace(max(0, a), min(N, b), 8)): needs.setdefault(int(round(fi)), []).append((("ev", ei, q), box))
        LOG("取帧:", sum(len(v) for v in needs.values()), "张,涉及", len(needs), "帧"); got = grab_frames(args.video, info, RW, RH, needs, out)
        per = 12; sheets = []
        for s in range(0, len(st), per):
            items = [(got[("sheet", k)], fmt_t(st[k])) for k in range(s, min(len(st), s + per)) if ("sheet", k) in got]
            if items: p = os.path.join(out, "sheets", "overview_%02d.jpg" % (s // per + 1)); cv2.imwrite(p, grid(items, 4, 480, "总览 %s - %s  (每 %.2fs 一帧)" % (fmt_t(st[s]), fmt_t(st[min(len(st) - 1, s + per - 1)]), step)), [cv2.IMWRITE_JPEG_QUALITY, 88]); sheets.append(os.path.relpath(p, out))
        for mi, m in enumerate(moves):
            items = []
            for q, fi in enumerate(np.linspace(m["i0"], min(N, m["i1"]), 8)):
                if ("move", mi, q) in got: items.append((got[("move", mi, q)], fmt_t(fi / fps)))
            if items:
                p = os.path.join(out, "moves", "move_%02d_t%.2f.jpg" % (mi + 1, m["t0"])); hd = "镜头运动 #%d  %.2f-%.2fs  %s  zoom×%.2f  峰值@%.0f%%  贝塞尔(%s)" % (mi + 1, m["t0"], m["t1"], m["kind"], m["zoom_factor"], m["peak_frac"] * 100, ",".join("%.2f" % x for x in m["bezier"]))
                cv2.imwrite(p, grid(items, 4, 480, hd), [cv2.IMWRITE_JPEG_QUALITY, 88]); m["image"] = os.path.relpath(p, out)
        for ei in sel:
            e = events[ei]; items = []
            for q, fi in enumerate(np.linspace(max(0, e["i0"] - int(0.06 * fps)), min(N, e["i1"] + int(0.10 * fps)), 8)):
                if ("ev", ei, q) in got: items.append((got[("ev", ei, q)], fmt_t(fi / fps)))
            if items:
                p = os.path.join(out, "events", "ev_%02d_t%.2f.jpg" % (ei + 1, e["t0"])); hd = "动效 #%d  %.2f-%.2fs  %s  区域=%s" % (ei + 1, e["t0"], e["t1"], e["guess"], e["bbox"])
                cv2.imwrite(p, grid(items, 4, 480, hd), [cv2.IMWRITE_JPEG_QUALITY, 88]); e["image"] = os.path.relpath(p, out)
        files_idx["sheets"] = sheets
        timeline_png(os.path.join(out, "timeline.png"), dur, fps, spd[:, 0], moves, events, tracks, audio)
    # ---------------- 同步统计
    sync = None
    if audio and audio["onsets"]:
        on = np.array([o["t"] for o in audio["onsets"] if o["strength"] >= 0.5]); hits = [m["t0"] for m in moves] + [e["t0"] for e in events] + [t["t_first"] for t in tracks]
        if len(on) and hits:
            near_fn = lambda t: float(np.min(np.abs(on - t))) <= 0.12; dts = np.array([(on[np.argmin(np.abs(on - h))] - h) for h in hits]); near = np.abs(dts) <= 0.12
            chance = float(np.mean([near_fn(t) for t in np.random.default_rng(0).uniform(0, dur, 2000)]))      # 随机时间点的"踩点率"基线:重音很密时基线本身就很高
            sync = dict(hits=len(hits), within_120ms=int(near.sum()), rate=float(near.mean()), chance=chance, median_offset_ms=float(np.median(dts[near]) * 1000) if near.any() else None)
    # ---------------- 输出
    for tr in tracks: tr["t_first"] = round(tr["t_first"], 2); tr["t_last"] = round(tr["t_last"], 2)
    data = dict(info=info, ref_size=[RW, RH], texture_coverage=tex_med, cuts=cuts, moves=moves, drifts=drift_list, events=events, event_threshold=ethr, texts=tracks, palette=pal, palette_timeline=pal_t, color_stats=cs,
                audio=None if not audio else {k: v for k, v in audio.items() if k != "rms_db"}, sync=sync, files=files_idx)
    json.dump(data, open(os.path.join(out, "data.json"), "w"), ensure_ascii=False, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))
    write_report(out, args.video, data, dur, fps, RW, RH)
    LOG("完成 →", out)

def dirs(dx, dy):
    s = []
    if abs(dx) > 8: s.append("向右" if dx > 0 else "向左")
    if abs(dy) > 8: s.append("向下" if dy > 0 else "向上")
    return "".join(s) or "无平移"

def write_report(out, video, d, dur, fps, RW, RH):
    I = d["info"]; L = []; w = L.append
    w("# 视频拆解报告:%s\n" % os.path.basename(video))
    w("## 0. 基本信息\n\n%dx%d · %.3f fps · %.2fs · %s · %s · 音轨:%s · 报告坐标系 %dx%d(x向右,y向下,像素)\n" % (I["W"], I["H"], fps, dur, I["codec"], I["pix_fmt"], ("有 " + str(I["audio"])) if I["has_audio"] else "无", RW, RH))
    w("先看 `timeline.png`(一张图看全片节奏),再看 `sheets/overview_*.jpg`,最后按需看 `moves/`、`events/` 里的条带。\n")
    w("## 1. 切点 / 转场\n")
    c = d["cuts"]
    if c is None: w("未检测。\n")
    else: w("- 硬切点:%s\n- 淡入/淡出黑场点:%s\n" % (c["hard_cuts"] or "无(连续镜头)", c["fade_points"] or "无"))
    if d["texture_coverage"] < 0.2: w("> ⚠ 画面可跟踪纹理很少(特征点铺开程度 %.2f):背景多为纯色/黑,运动估计只能依赖少量亮点,镜头/物体的区分与位移数值可能不可靠,请以 moves/ events/ 条带目视为准。\n" % d["texture_coverage"])
    w("## 2. 画面运动(%d 次;范围=全局 的是镜头运动,=局部 的是卡片/元素自己在动,=不可信 的是持续过久/缩放离谱的伪运动)\n\n内容位移 = 画面内容在屏幕上移动的方向;镜头方向与之相反。zoom×>1 为推近。范围:全局=前景特征点铺满大半个画面(镜头/整屏运动),局部=只有一小块内容在动(卡片/元素的滑动、缩放),括号内为内点包围盒占画面比。贝塞尔为对累计位移曲线的拟合(CSS cubic-bezier,组合运动时为近似);峰值位置越靠前=起手越快、尾巴越长。\n" % len(d["moves"]))
    if d["moves"]:
        w("| # | 时间 | 时长 | 范围(前景覆盖) | 类型 | 镜头方向/位移px | zoom× | 峰值速度px/s | 峰值位置 | 拟合缓动 (RMSE) | 最接近预设 | 第2/3层速度比 | 条带 |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for k, m in enumerate(d["moves"]):
            ratio = " / ".join("%.2f" % r if r is not None else "-" for r in (m["layer2_ratio"], m["layer3_ratio"]))
            w("| %d | %.2f-%.2f | %.2fs | %s(%.2f) | %s | %s %d,%d | %.2f | %.0f | %.0f%% | (%s) %.3f | %s %.3f | %s | %s |" % (k + 1, m["t0"], m["t1"], m["dur"], m["scope"], m["spread"], m["kind"], dirs(m["cam_dx"], m["cam_dy"]), m["cam_dx"], m["cam_dy"], m["zoom_factor"], m["peak_px_s"], m["peak_frac"] * 100,
                                                                                    ",".join("%.2f" % x for x in m["bezier"]), m["bezier_rmse"], m["preset"], m["preset_rmse"], ratio, m.get("image", "")))
        w("")
    if d["drifts"]: w("慢速推拉/漂移:" + ";".join("%.1f-%.1fs zoom×%.2f 位移(%d,%d)" % (x["t0"], x["t1"], x["zoom_factor"], x["cam_dx"], x["cam_dy"]) for x in d["drifts"]) + "\n")
    w("## 3. 元素动效事件(运动补偿后的局部变化;共 %d 个,阈值 %.2f)\n\n类型是启发式猜测,以 `events/` 条带为准(条带已裁剪放大到动效发生的区域)。\n" % (len(d["events"]), d["event_threshold"]))
    w("| # | 时间 | 时长 | 区域 x0,y0,x1,y1 | 面积 | 推测类型 | 条带 |\n|---|---|---|---|---|---|---|")
    for k, e in enumerate(d["events"]): w("| %d | %.2f-%.2f | %.2fs | %s | %.0f%% | %s | %s |" % (k + 1, e["t0"], e["t1"], e["dur"], e["bbox"], e["area_frac"] * 100, e["guess"], e.get("image", "")))
    w("\n## 4. 屏幕文字(OCR 轨迹)\n")
    if d["texts"]:
        w("| 文字 | 出现-消失 | 位置 x0,y0,x1,y1 | 字高px(占画面高%) | 文字色/底色 | 备注 |\n|---|---|---|---|---|---|")
        for t in sorted(d["texts"], key=lambda t: t["t_first"]):
            note = ("逐字打出 %s 字/s" % t["chars_per_s"]) if t["typed"] else ""
            w("| %s | %.2f-%.2f | %s | %.0f (%.1f%%) | %s / %s | %s |" % (t["text"].replace("|", "/"), t["t_first"], t["t_last"], [int(x) for x in t["bbox"]], t["height"], t["height"] / RH * 100, t.get("color", "-"), t.get("bg", "-"), note))
        hs = sorted({round(t["height"] / 4) * 4 for t in d["texts"] if t["height"] >= 10}, reverse=True)
        w("\n字高层级(px,去重):%s;相邻层级比:%s\n" % (hs, [round(hs[i] / hs[i + 1], 2) for i in range(len(hs) - 1)][:12]))
        lefts = sorted(int(t["bbox"][0]) // 20 * 20 for t in d["texts"]); from collections import Counter
        w("左边缘对齐线(每 20px 归并,出现次数最多):%s\n" % Counter(lefts).most_common(5))
    else: w("未启用或未识别到文字。\n")
    w("## 5. 配色\n\n整体:平均亮度 %.0f/255 · 平均饱和度 %.2f · 饱和度P90 %.2f · 对比度(灰度标准差) %.0f\n" % (d["color_stats"]["mean_luma"], d["color_stats"]["mean_sat"], d["color_stats"]["sat_p90"], d["color_stats"]["contrast"]))
    w("全片主色:" + "  ".join("`%s` %.0f%%(L%.0f C%.0f)" % (c["hex"], c["pct"], c["L"], c["chroma"]) for c in d["palette"]) + "\n")
    for p in d["palette_timeline"]: w("- %.0f-%.0fs:%s" % (p["t0"], p["t1"], "  ".join("`%s` %.0f%%" % (c["hex"], c["pct"]) for c in p["colors"])))
    w("\n## 6. 音频\n")
    a = d["audio"]
    if a:
        w("响度 %s · 估计节拍 %s BPM · 检测到 %d 个重音(onset)。强重音时间(s):%s\n" % (a["loudness"], a["bpm"], len(a["onsets"]), [o["t"] for o in a["onsets"] if o["strength"] >= 1.0][:40]))
        if d["sync"]: w("画面事件(镜头运动起点 / 元素动效起点 / 文字出现)与音频重音在 ±120ms 内对齐:%d/%d = %.0f%%(随机时间点的基线 %.0f%%;只有明显高于基线才说明画面在踩点,接近基线=没有刻意对齐),落在窗内的事件中位偏移 %s ms(负=画面早于声音)\n" % (d["sync"]["within_120ms"], d["sync"]["hits"], d["sync"]["rate"] * 100, d["sync"]["chance"] * 100, ("%.0f" % d["sync"]["median_offset_ms"]) if d["sync"]["median_offset_ms"] is not None else "-"))
    else: w("无音轨或未分析。\n")
    w("## 7. 合并时间线(镜头运动 / 元素动效 / 文字出现)\n")
    ev = [(m["t0"], "镜头", "#%d %s 位移(%d,%d) zoom×%.2f 耗时%.2fs" % (k + 1, m["kind"], m["cam_dx"], m["cam_dy"], m["zoom_factor"], m["dur"])) for k, m in enumerate(d["moves"])]
    ev += [(e["t0"], "动效", "#%d %s 区域%s %.2fs" % (k + 1, e["guess"], e["bbox"], e["dur"])) for k, e in enumerate(d["events"])] + [(t["t_first"], "文字", "“%s” 字高%.0f%s" % (t["text"], t["height"], " 逐字打出" if t["typed"] else "")) for t in d["texts"]]
    for t, k, s in sorted(ev): w("- %s  [%s] %s" % (fmt_t(t), k, s))
    open(os.path.join(out, "report.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")

if __name__ == "__main__": main()
