"""网页场景页(03_scene.html)的自动版面检查,由 check.py 调用。

做法:多开几个无界面 Chrome,每 0.1 秒 seek 一次,在页面里收集「可见文字」的屏幕矩形
(累计 opacity>0.6、累计 blur<2px、至少一半在画面内),再在 Python 里汇总四类问题:
  出画/贴边(四周 30px 安全边距,只在文字静止时算,飞镜途中不算)
  被遮挡(完整出现后 0.5 秒内,文字矩形内 5 个采样点里 ≥2 个被别的元素压住;同一个 .hz-ui 组件内部的元素不算)
  文字重叠(两段可见文字的矩形互相压住;同一个 .hz-ui 组件内部的行不互相比)
  展示不足(从完整出现到消失/虚化不足 0.6 秒)
  动画出画(文字从开始出现到完整出现后 0.6 秒,有一部分在画面外 = 观众看不到它的动画)
另外每帧量一次「看得清的 UI/截图」占画面的比例(.hz-ui / img / video / canvas,累计 opacity≥0.5、模糊≤3px),
并读出 hz_kit.js 记下的交互动画清单 hz.k.log,给规范 v2 的「案例段有没有 UI、有没有交互」用(见 check.py)。
文字 = .hz-txt 元素(data-t0 = 完整出现时刻);页面里一个 .hz-txt 都没有时,退回「有直接文本内容的元素」,
完整出现时刻取「累计 opacity≥0.95 且不虚化」的第一帧。
"""
import os, time, json
from multiprocessing.pool import ThreadPool   # 浏览器在各自进程里跑,这边只是等 socket,线程就够
from pathlib import Path
from _cdp import Browser

STEP = 0.1; MARGIN = 30; VIS_OP = 0.6; FULL_OP = 0.95; BLUR = 2.0
OCC_WIN = 0.5; MIN_SHOW = 0.6

PROBE = r"""
(async (t, W, H) => {
  await window.HZ.seek(t);
  await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
  let els = Array.from(document.querySelectorAll('.hz-txt'));
  const fallback = els.length === 0;
  if (fallback) {
    const skip = new Set(['SCRIPT','STYLE','TITLE','HEAD','NOSCRIPT','svg','SVG','TEXTAREA','OPTION']);
    els = Array.from(document.body.querySelectorAll('*')).filter(e => !skip.has(e.tagName) &&
      Array.from(e.childNodes).some(n => n.nodeType === 3 && n.textContent.trim()));
    // 只留最外层:祖先已经是文字候选的,并到祖先里
    const S = new Set(els); els = els.filter(e => { for (let p = e.parentElement; p; p = p.parentElement) if (S.has(p)) return false; return true; });
  }
  const path = e => { const a = []; for (; e && e !== document.body; e = e.parentElement) { let i = 0, s = e; while ((s = s.previousElementSibling)) i++; a.push(i); } return a.reverse().join('.'); };
  const cs = new Map(); const st = e => { let s = cs.get(e); if (!s) { s = getComputedStyle(e); cs.set(e, s); } return s; };
  const eff = e => { let op = 1, bl = 0; for (; e && e.nodeType === 1; e = e.parentElement) { const s = st(e);
      if (s.display === 'none') return [0, 0]; op *= parseFloat(s.opacity);
      const m = (s.filter || '').match(/blur\(([\d.]+)px\)/); if (m) bl += parseFloat(m[1]); }
    return [op, bl]; };
  const MEDIA = new Set(['IMG','CANVAS','IFRAME','VIDEO','svg','path','circle','rect','polygon','ellipse','line','polyline','use','image','text']);
  const paints = (h, x, y) => {
    if (MEDIA.has(h.tagName) || h.classList.contains('hz-card') || h.classList.contains('hz-txt')) return true;
    const s = st(h); const bg = s.backgroundColor.match(/[\d.]+/g);
    if (bg && (bg.length < 4 || parseFloat(bg[3]) > 0.1)) return true;
    if (s.backgroundImage && s.backgroundImage !== 'none') return true;
    if (Array.from(h.childNodes).some(n => n.nodeType === 3 && n.textContent.trim())) {
      const rg = document.createRange(); rg.selectNodeContents(h);
      for (const q of rg.getClientRects()) if (x >= q.left && x <= q.right && y >= q.top && y <= q.bottom) return true;
    }
    return false;
  };
  const out = [], part = [];
  for (const e of els) {
    if (st(e).visibility === 'hidden') continue;
    const [op, bl] = eff(e); if (op <= 0.05) continue;
    const rg = document.createRange(); rg.selectNodeContents(e); const r = rg.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) continue;
    // 已经开始出现(哪怕还很淡/很虚)却有一块在画面外 → 记下来,给「动画出画」用
    if (e.dataset && e.dataset.t0 !== undefined && (r.left < 0 || r.top < 0 || r.right > W || r.bottom > H))
      part.push([path(e), (e.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 30), parseFloat(e.dataset.t0),
                 Math.round(r.left), Math.round(r.top), Math.round(r.right), Math.round(r.bottom)]);
    if (op <= %VIS% || bl >= %BLUR%) continue;
    const ix = Math.max(0, Math.min(r.right, W) - Math.max(r.left, 0)), iy = Math.max(0, Math.min(r.bottom, H) - Math.max(r.top, 0));
    if (ix * iy < 0.5 * r.width * r.height) continue;
    const txt = (e.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 30); if (!txt) continue;
    // 遮挡采样:5 个点,用 elementsFromPoint 从上往下找,透明的容器跳过,
    // 先碰到「会画东西」的别的元素(有底色/背景图/图片/svg/iframe/文字本身…)→ 这点被压住
    let occ = 0, np = 0, by = ''; const u = e.closest('.hz-ui');
    for (const [fx, fy] of [[.5,.5],[.2,.3],[.8,.3],[.2,.7],[.8,.7]]) {
      const x = r.left + r.width * fx, y = r.top + r.height * fy; if (x < 0 || y < 0 || x >= W || y >= H) continue;
      np++;
      for (const h of document.elementsFromPoint(x, y)) {
        if (e.contains(h) || h.contains(e)) break;
        if (u && u.contains(h)) continue;   // 同一个 UI 组件内部的层次(高亮条、相邻行)由组件自己管
        if (!paints(h, x, y) || eff(h)[0] < 0.3) continue;
        occ++; if (!by) { const tc = (h.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 16);
          by = h.tagName.toLowerCase() + (h.classList.length ? '.' + Array.from(h.classList).join('.') : '') + (tc ? ' 「' + tc + '」' : ''); }
        break;
      }
    }
    const t0 = e.dataset && e.dataset.t0 !== undefined ? parseFloat(e.dataset.t0) : null;
    out.push([path(e), txt, Math.round(r.left), Math.round(r.top), Math.round(r.right), Math.round(r.bottom),
              +op.toFixed(3), +bl.toFixed(2), occ, by, t0, np, u ? path(u) : '']);
  }
  // 看得清的 UI/截图占画面多少(嵌套的只算最外层)
  let ua = 0; const done = [];
  for (const e of document.querySelectorAll('.hz-ui, img, video, canvas')) {
    if (done.some(p => p.contains(e)) || st(e).visibility === 'hidden') continue;
    const [op, bl] = eff(e); if (op < 0.5 || bl > 3) continue;
    const r = e.getBoundingClientRect();
    const ix = Math.max(0, Math.min(r.right, W) - Math.max(r.left, 0)), iy = Math.max(0, Math.min(r.bottom, H) - Math.max(r.top, 0));
    if (ix * iy < 1) continue; ua += ix * iy; done.push(e);
  }
  return {fallback, items: out, part, ui: Math.min(1, ua / (W * H))};
})
"""


def _open(ep, page, w, h):
    b = Browser(w, h, proxy=os.environ.get("HZ_PROXY", "127.0.0.1:7897"))
    b.goto(Path(ep, page).resolve().as_uri(),
           "window.HZ && window.HZ.ready === true && document.fonts.status==='loaded'", timeout=60)
    return b


def _worker(args):
    ep, page, w, h, ts = args
    b = _open(ep, page, w, h); res = []
    fn = PROBE.replace("%VIS%", str(VIS_OP)).replace("%BLUR%", str(BLUR))
    try:
        for t in ts:
            r = b.js(f"{fn}({t:.3f},{w},{h})"); res.append((t, r["fallback"], r["items"], r["ui"]))
    finally:
        b.close()
    return res


def _spaced(xs, gap=1.5):
    out = []
    for x in xs:
        if not out or x - out[-1] >= gap: out.append(round(x, 2))
    return out


def check_web(ep, page, w, h, workers=4, t_range=None):
    """返回 (问题字符串列表, 明细列表, 统计)。t_range=(起, 止) 只查这一段(前后各多查 0.6 秒)。"""
    T0 = time.time()
    b = _open(ep, page, w, h); dur = float(b.js("window.HZ.dur"))
    klog = b.js("JSON.stringify((window.hz && window.hz.k && window.hz.k.log) || null)"); b.close()
    ts = [round(i * STEP, 3) for i in range(int(dur / STEP) + 1) if i * STEP <= dur - 0.02]
    if t_range: ts = [t for t in ts if t_range[0] - 0.6 <= t <= t_range[1] + 0.6]
    n = max(1, min(workers, len(ts)))
    k = (len(ts) + n - 1) // n; chunks = [ts[i:i + k] for i in range(0, len(ts), k)]
    with ThreadPool(len(chunks)) as pool:
        samples = sorted(sum(pool.map(_worker, [(ep, page, w, h, c) for c in chunks]), []))
    fallback = any(s[1] for s in samples)

    # 每段文字的逐帧轨迹: id -> {t: item}
    tr = {}
    for t, _, items, _u in samples:
        for it in items: tr.setdefault(it[0], {})[t] = it
    idx = {t: i for i, t in enumerate(ts)}
    det = []

    def add(kind, t, txt, msg, **kw):
        det.append(dict(type=kind, t=round(t, 2), text=txt, msg=msg, **kw))

    def full(it): return it[6] >= FULL_OP and it[7] < 0.5
    def hid(it): return it[11] > 0 and it[8] >= 0.8 * it[11]          # 几乎整块被上层压住 = 看不见
    def vis(it): return not hid(it)

    for key, fr in tr.items():
        tl = sorted(fr); txt = fr[tl[0]][1]
        V = {t for t in tl if vis(fr[t])}
        # 完整出现时刻:data-t0 优先;否则「看得见且累计 opacity≥0.95」的各段起点
        dt0 = next((fr[t][10] for t in tl if fr[t][10] is not None), None)
        starts = []
        if dt0 is not None:
            s0 = min((t for t in ts if t >= dt0 - 1e-6), default=None)
            if s0 is not None: starts = [s0]
        else:
            prev = False
            for t in ts:
                f = t in V and full(fr[t])
                if f and not prev: starts.append(t)
                prev = f
        for s0 in starts:
            occ_hit = None
            for t in ts[idx[s0]:]:
                if t > s0 + OCC_WIN + 1e-6: break
                it = fr.get(t)
                if it is not None and it[8] >= 2: occ_hit = (t, it); break
            if occ_hit:
                t, it = occ_hit
                add("被遮挡", t, txt, f"{s0:.2f}s 完整出现,{t:.2f}s 被 {it[9]} 挡住({it[8]}/{it[11]} 个采样点)")
                continue
            if s0 not in V: continue
            i = idx[s0]
            while i + 1 < len(ts) and ts[i + 1] in V: i += 1
            gone = ts[i + 1] if i + 1 < len(ts) else None
            if gone is not None and gone - s0 < MIN_SHOW - 1e-6 and s0 > 0.05:
                add("展示不足", s0, txt, f"{s0:.2f}s 完整出现,{gone:.2f}s 就消失/虚化/被盖住,只展示 {gone - s0:.1f} 秒(要 ≥{MIN_SHOW})")
        # 出画/贴边:只在文字静止(和上一帧比移动 <1.5px)、看得见且不透明时算;连续一段只报一次
        run = False
        for t in tl:
            it = fr[t]; pv = fr.get(round(t - STEP, 3))
            still = pv is not None and max(abs(a - b) for a, b in zip(it[2:6], pv[2:6])) < 1.5
            L, T_, R, B = it[2:6]
            out = L < 0 or T_ < 0 or R > w or B > h
            edge = L < MARGIN or T_ < MARGIN or R > w - MARGIN or B > h - MARGIN
            bad = still and full(it) and vis(it) and edge
            if bad and not run:
                kind = "出画" if out else "贴边"
                add(kind, t, txt, f"{kind}  x[{L},{R}] y[{T_},{B}],画面 {w}x{h},安全边距 {MARGIN}px", rect=[L, T_, R, B])
            run = bad

    # 两段看得见的文字互相压住:两段都不透明、且连续 ≥0.2 秒(飞镜/转场途中一闪而过的不算);同一对连续一段只报一次
    hits = {}
    for t, _, items, _u in samples:
        Vs = [it for it in items if vis(it) and full(it)]
        for i in range(len(Vs)):
            for j in range(i + 1, len(Vs)):
                a, b_ = Vs[i], Vs[j]
                if a[0].startswith(b_[0] + ".") or b_[0].startswith(a[0] + "."): continue
                if a[12] and a[12] == b_[12]: continue   # 同一个 UI 组件(代码块/终端/列表)里的行由组件自己排版,带透视时外接框会互相压几像素,不算重叠
                ox = min(a[4], b_[4]) - max(a[2], b_[2])
                # 矩形是字体的行盒(含上下留白),上下各收 12% 近似字形墨迹,避免大字号「贴得近」误报
                ia, ib = 0.12 * (a[5] - a[3]), 0.12 * (b_[5] - b_[3])
                oy = round(min(a[5] - ia, b_[5] - ib) - max(a[3] + ia, b_[3] + ib))
                small = min((a[4] - a[2]) * (a[5] - a[3]), (b_[4] - b_[2]) * (b_[5] - b_[3]))
                if ox > 4 and oy > 4 and ox * oy > 0.05 * small:
                    hits.setdefault((a[0], b_[0]), []).append((t, a[1], b_[1], ox, oy))
    for pair, L in hits.items():
        run = [L[0]]
        for x in L[1:] + [None]:
            if x is not None and abs(x[0] - run[-1][0] - STEP) < 1e-6: run.append(x); continue
            if len(run) >= 2:
                t, ta, tb, ox, oy = run[0]
                add("文字重叠", t, ta, f"「{ta}」×「{tb}」重叠 {ox}×{oy}px,持续 {run[-1][0] - t + STEP:.1f} 秒", other=tb)
            if x is not None: run = [x]

    det.sort(key=lambda d: (d["t"], d["type"]))
    lines = [f"[{d['t']:.2f}s] {d['type']} 「{d['text']}」 {d['msg']}" for d in det]
    stat = dict(dur=dur, samples=len(ts), texts=len(tr), fallback=fallback, workers=len(chunks),
                seconds=round(time.time() - T0, 1), range=list(t_range) if t_range else None,
                ui=[(t, round(u, 4)) for t, _f, _i, u in samples], klog=json.loads(klog) if klog else None,
                appear=_spaced(sorted(min(fr) for fr in tr.values())))
    return lines, det, stat
