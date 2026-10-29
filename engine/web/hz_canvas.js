/* hz_canvas.js —— 升级版无限画布 + 文字动效(在 hz.js 之后加载)。说明见 engine/web/CANVAS.md。
   手感对齐老 Python 引擎(ci.py):van Wijk 缩放平移飞行、E_EXPO 快起慢停、焦点层级 L 驱动虚化/压暗/降饱和/后退。
   颜色只取 CSS 变量:--c-bg --c-ink --c-mute --c-main --c-accent --c-warn。 */
(function () {
  const hz = window.hz;
  if (!hz) throw new Error("hz_canvas.js 必须在 hz.js 之后加载");
  const $ = hz.$, clamp = hz.clamp, lerp = hz.lerp;
  const smooth = (x) => { x = clamp(x); return x * x * (3 - 2 * x); };
  const EXPO = hz.bez(0.16, 1, 0.3, 1);       // 老引擎 E_EXPO
  const EOUT = hz.bez(0.22, 1, 0.36, 1);      // 老引擎 E_OUT
  const EINOUT = hz.bez(0.76, 0, 0.24, 1);    // 老引擎 E_INOUT
  hz.ease.expo = EXPO; hz.ease.out2 = EOUT; hz.ease.inout2 = EINOUT;
  const ev = (e, dt, d) => (e && e.spring ? e.f(dt) : (e || EOUT)(clamp(dt / d)));

  // ---------- 注入基础样式(颜色全部走变量) ----------
  const css = `
  :root{--c-bg:#141214;--c-ink:#EDE6DA;--c-mute:#8E877B;--c-main:#9B7BFF;--c-accent:#3FD0C9;--c-warn:#FF8A3D}
  .hz-stage3d{position:absolute;inset:0;perspective:var(--hz-persp,1800px);perspective-origin:50% 50%;pointer-events:none}
  .hz-tilt{position:absolute;inset:0;transform-origin:50% 50%}
  .hz-world{position:absolute;left:0;top:0;width:0;height:0;transform-origin:0 0}
  .hz-node{position:absolute;width:0;height:0;transform-origin:0 0}
  .hz-blob{position:absolute;border-radius:50%;pointer-events:none}
  .hz-at{position:absolute;transform:translate(-50%,-50%);white-space:nowrap}
  .hz-txt{white-space:nowrap;color:var(--c-ink)}
  .hz-ch{display:inline-block;white-space:pre;will-change:transform,filter,opacity}
  .hz-grad .hz-ch,.hz-grad.hz-gradself{background:linear-gradient(180deg,var(--c-ink) 18%,color-mix(in srgb,var(--c-ink) 58%,var(--c-bg)) 92%);-webkit-background-clip:text;background-clip:text;color:transparent}
  .hz-shadow{filter:drop-shadow(0 0.04em 0.05em rgba(0,0,0,.45))}
  .hz-cbar{position:absolute;top:50%;width:0.055em;height:1.08em;margin-top:-0.56em;border-radius:0.04em;background:var(--hz-caret,var(--c-main))}
  .hz-cwrap{display:inline-block;position:relative;width:0;height:1em;vertical-align:baseline}
  .hz-cwrap .hz-cbar{left:0.04em;top:auto;bottom:-0.16em;margin:0}
  .hz-odo{display:inline-flex;align-items:baseline;font-variant-numeric:tabular-nums}
  .hz-col{display:inline-block;position:relative;width:1ch;height:1em;line-height:1em;overflow:hidden;
    -webkit-mask-image:linear-gradient(180deg,transparent 0,#000 18%,#000 82%,transparent 100%);mask-image:linear-gradient(180deg,transparent 0,#000 18%,#000 82%,transparent 100%)}
  .hz-col>span{position:absolute;left:0;top:0;width:100%;text-align:center}
  .hz-sep{display:inline-block}
  .hz-hlw{position:relative;display:inline-block;isolation:isolate}
  .hz-stroke{position:absolute;left:-0.08em;z-index:-1;border-radius:0.5em 0.35em 0.55em 0.3em/0.6em 0.45em 0.6em 0.5em;transform:rotate(-0.8deg);transform-origin:0 50%}
  .hz-pill{display:inline-flex;align-items:center;gap:0.5em;padding:0.42em 0.95em;border-radius:999px;white-space:nowrap;
    background:color-mix(in srgb,var(--hz-pc,var(--c-main)) 16%,color-mix(in srgb,var(--c-bg) 80%,transparent));
    box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--hz-pc,var(--c-main)) 42%,transparent),0 0.5em 1.2em -0.5em rgba(0,0,0,.55);color:var(--c-ink)}
  .hz-pill i{display:block;width:0.42em;height:0.42em;border-radius:50%;background:var(--hz-pc,var(--c-main))}
  .hz-caps{text-transform:uppercase;letter-spacing:var(--hz-track,0.32em);color:var(--c-mute);font-weight:500}
  `;
  const st = document.createElement("style"); st.textContent = css; document.head.prepend(st);

  // ---------- 小工具 ----------
  const mk = (tag, cls, parent, css2) => { const e = document.createElement(tag); if (cls) e.className = cls; if (css2) e.style.cssText = css2; if (parent) parent.appendChild(e); return e; };
  hz.mk = mk;
  // 在 parent(一般是节点)里放一个以 (x,y) 为中心的元素;o.z 视差层,o.cls 类名,o.html 内容,o.css 额外样式
  hz.put = (parent, x, y, o = {}) => {
    const e = mk(o.tag || "div", "hz-at " + (o.cls || ""), $(parent), o.css || "");
    e.style.left = x + "px"; e.style.top = y + "px";
    if (o.z) e.dataset.z = o.z;
    if (o.html != null) e.innerHTML = o.html;
    return e;
  };
  const mark = (el, tFull) => { el.classList.add("hz-txt"); el.dataset.t0 = (+tFull).toFixed(3); };

  // van Wijk 缩放-平移插值(移植自 ci.py vw_interp;w = 画面宽 / 缩放)
  function vw(c0, w0, c1, w1, f, rho = 1.25) {
    const dx = c1[0] - c0[0], dy = c1[1] - c0[1], u1 = Math.hypot(dx, dy);
    if (u1 < 1e-6) return [c0[0], c0[1], w0 * Math.pow(w1 / w0, f)];
    const b0 = (w1 * w1 - w0 * w0 + rho ** 4 * u1 * u1) / (2 * w0 * rho * rho * u1);
    const b1 = (w1 * w1 - w0 * w0 - rho ** 4 * u1 * u1) / (2 * w1 * rho * rho * u1);
    const r0 = Math.log(-b0 + Math.sqrt(b0 * b0 + 1)), r1 = Math.log(-b1 + Math.sqrt(b1 * b1 + 1)), S = (r1 - r0) / rho, s = f * S;
    const u = (w0 / (rho * rho)) * Math.cosh(r0) * Math.tanh(rho * s + r0) - (w0 / (rho * rho)) * Math.sinh(r0);
    const w = (w0 * Math.cosh(r0)) / Math.cosh(rho * s + r0);
    return [c0[0] + (dx / u1) * u, c0[1] + (dy / u1) * u, w];
  }
  hz.vw = vw;

  // ---------- 无限画布 ----------
  const overrides = [];
  hz.cam = { x: 0, y: 0, z: 1, rx: 0, ry: 0, i: 0 };
  hz.canvas = (world, nodes, o = {}) => {
    world = $(world);
    const W = o.W || innerWidth || 1920, H = o.H || innerHeight || 1080;
    const ramp = o.ramp ?? 0.8, rho = o.rho ?? 1.25, dip = o.dip ?? 0.04, par = o.parallax ?? 0.06;
    // 结构:stage3d(透视) > tilt(整张画布 3D 倾斜) > world(缩放平移)
    const stage = mk("div", "hz-stage3d"); world.parentNode.insertBefore(stage, world);
    if (o.persp) stage.style.setProperty("--hz-persp", o.persp + "px");
    const tilt = mk("div", "hz-tilt", stage); tilt.appendChild(world); world.classList.add("hz-world");
    const blobL = mk("div", "", world, "position:absolute;left:0;top:0;width:0;height:0"); world.prepend(blobL);
    const blobs = [];
    nodes.forEach((n, i) => {
      if (!n.el) n.el = mk("div", "", world);
      n.el.classList.add("hz-node"); n.el.style.left = n.x + "px"; n.el.style.top = n.y + "px";
      n.zoom = n.zoom || 1; n.flight = n.flight ?? (i ? 0.75 : 0.01); n.pre = n.pre ?? 0.75; n.e = n.e || EXPO;
      n.drift = n.drift || [0.01, 0, 0]; n.rx = n.rx || 0; n.ry = n.ry || 0; n.fade = n.fade ?? 1; n.z = n.z || 0;
      n._par = [...n.el.querySelectorAll("[data-z]")].map((e) => ({ e, lx: parseFloat(e.style.left) || 0, ly: parseFloat(e.style.top) || 0 }));
      [].concat(n.blob || []).forEach((b) => {
        const r = b.r || 900, d = mk("div", "hz-blob", blobL);
        d.style.cssText += `left:${n.x + (b.dx || 0) - r}px;top:${n.y + (b.dy || 0) - r}px;width:${2 * r}px;height:${2 * r}px;` +
          `background:radial-gradient(closest-side,${b.c || "var(--c-main)"} 0%,color-mix(in srgb,${b.c || "var(--c-main)"} 40%,transparent) 45%,transparent 100%);mix-blend-mode:${b.blend || "screen"}`;
        blobs.push({ d, n, i, a: b.a ?? 0.12, z: b.z ?? -3, wx: n.x + (b.dx || 0), wy: n.y + (b.dy || 0) });
      });
    });
    const start = (n) => n.t - n.flight * n.pre;
    // 节点到位后的镜头:段内关键帧(依次累积)+ 漂移
    const rest = (n, t) => {
      let c = [0, 0, 1, n.rx, n.ry], out = c.slice();
      for (const k of n.keys || []) {
        if (t < k.t0) break;
        const f = (k.e || EINOUT)(clamp((t - k.t0) / Math.max(1e-6, k.t1 - k.t0)));
        const g = [k.x ?? c[0], k.y ?? c[1], k.zoom ?? c[2], k.rx ?? c[3], k.ry ?? c[4]];
        out = [lerp(c[0], g[0], f), lerp(c[1], g[1], f), Math.exp(lerp(Math.log(c[2]), Math.log(g[2]), f)), lerp(c[3], g[3], f), lerp(c[4], g[4], f)];
        if (t >= k.t1) c = g; else break;
      }
      const dt = Math.max(0, t - n.t);
      return [n.x + out[0] + n.drift[1] * dt, n.y + out[1] + n.drift[2] * dt, n.zoom * out[2] * (1 + n.drift[0] * dt), out[3], out[4]];
    };
    hz.canvasNodes = nodes;
    hz.every((t) => {
      nodes.forEach((n, j) => {
        let L = 0; for (const m of nodes.slice(j + 1)) L += smooth((t - start(m)) / ramp);
        n.L = L; n._vis = L < 3 && t >= start(n) - (n.lead ?? 1.0) && (n.t1 == null || t < n.t1);
        n.el.style.display = n._vis ? "" : "none";
      });
      let i = 0; for (let j = 0; j < nodes.length; j++) if (start(nodes[j]) <= t) i = j;
      const b = nodes[i]; let [x, y, z, rx, ry] = rest(b, t);
      if (i > 0 && t < start(b) + b.flight) {
        const a = nodes[i - 1], ts = start(b), u = clamp((t - ts) / b.flight), f = ev(b.e, t - ts, b.flight);
        const A = rest(a, ts), B = rest(b, ts + b.flight);
        const r = vw([A[0], A[1]], W / A[2], [B[0], B[1]], W / B[2], f, rho);
        x = r[0]; y = r[1]; z = (W / r[2]) * (1 - dip * Math.sin(Math.PI * u));
        const bump = Math.sin(Math.PI * Math.pow(u, 0.8));
        rx = lerp(A[3], B[3], f) + (b.tilt ? b.tilt.rx || 0 : 0) * bump;
        ry = lerp(A[4], B[4], f) + (b.tilt ? b.tilt.ry || 0 : 0) * bump;
      }
      // camTo 覆盖
      for (const ov of overrides) {
        if (t < ov.t0) continue;
        let u = ev(ov.e, t - ov.t0, ov.d);
        if (ov.t1 != null && t >= ov.t1) u = 1 - ev(ov.e, t - ov.t1, ov.back);
        if (u <= 0) continue;
        const R = ov.rect ? ov.rect : measure(ov.el, world, tilt, nodes);
        if (!R || R.w < 2 || R.h < 2) continue;
        if (ov.freeze) ov.rect = R;
        const tz = Math.min((W * ov.fill) / R.w, (H * ov.fill) / R.h) * (ov.zmul || 1);
        const r = vw([x, y], W / z, [R.x + R.w / 2 + (ov.dx || 0), R.y + R.h / 2 + (ov.dy || 0)], W / tz, u, rho);
        x = r[0]; y = r[1]; z = W / r[2]; rx = lerp(rx, ov.rx ?? 0, u); ry = lerp(ry, ov.ry ?? 0, u);
      }
      hz.cam = { x, y, z, rx, ry, i };
      tilt.style.transform = Math.abs(rx) + Math.abs(ry) > 0.01 ? `rotateX(${rx}deg) rotateY(${ry}deg)` : "none";
      world.style.transform = `translate(${W / 2}px,${H / 2}px) scale(${z}) translate(${-x}px,${-y}px)`;
      // 焦点层级
      nodes.forEach((n, j) => {
        const L = n.L;
        if (!n._vis) return;
        const f = n.fade, L1 = Math.min(L, 1), L2 = clamp(L - 1);
        const sig = (10 * L1 + 12 * L2) * f / Math.max(0.2, z);
        const br = 1 - (0.55 * L1 + 0.22 * L2) * f, sat = 1 - 0.45 * L1 * f;
        n.el.style.filter = sig > 0.08 ? `blur(${sig.toFixed(2)}px) brightness(${br.toFixed(3)}) saturate(${sat.toFixed(3)})` : "none";
        n.el.style.opacity = 1 - smooth(L - 2);
        const k = (1 - 0.06 * Math.min(L, 2) * f) * (1 + par * n.z);
        n.el.style.transform = Math.abs(k - 1) > 1e-4 ? `translate(${(n.x - x) * (k - 1)}px,${(n.y - y) * (k - 1)}px) scale(${k})` : "none";
        for (const p of n._par) {
          const kz = 1 + par * +p.e.dataset.z;
          p.e.style.translate = `${(n.x + p.lx - x) * (kz - 1)}px ${(n.y + p.ly - y) * (kz - 1)}px`; p.e.style.scale = kz;
        }
      });
      for (const bl of blobs) {
        const n = bl.n, win = bl.i ? smooth((t - start(n)) / Math.max(0.3, n.flight)) : 1;
        bl.d.style.opacity = bl.a * win * (1 - smooth(Math.min(n.L, 1)));
        const kz = 1 + par * bl.z;
        bl.d.style.transform = `translate(${(bl.wx - x) * (kz - 1)}px,${(bl.wy - y) * (kz - 1)}px)`;
      }
    });
    return { stage, tilt, world, nodes };
  };

  // 某元素在世界坐标里的矩形 {x,y,w,h}(暂时去掉镜头/倾斜/后退变换后量取)
  function measure(el, world, tilt, nodes) {
    el = $(el); if (!el) return null;
    tilt.style.transform = "none"; world.style.transform = "none";
    const saved = nodes.map((n) => n.el.style.transform); nodes.forEach((n) => (n.el.style.transform = "none"));
    const wr = world.getBoundingClientRect(), r = el.getBoundingClientRect();
    nodes.forEach((n, i) => (n.el.style.transform = saved[i]));
    return { x: r.left - wr.left, y: r.top - wr.top, w: Math.max(1, r.width), h: Math.max(1, r.height) };
  }
  // 镜头在 t0 起飞到某元素(或 {x,y,w,h} 世界矩形),d 秒到位;o.t1 给了就在 t1 起飞返回原镜头
  hz.camTo = (target, t0, o = {}) => {
    const ov = { t0, d: o.d ?? 0.8, e: o.e || EXPO, fill: o.fill ?? 0.72, t1: o.t1 ?? null, back: o.back ?? 0.8, rx: o.rx, ry: o.ry, dx: o.dx, dy: o.dy, zmul: o.zmul, freeze: o.freeze ?? true };
    if (target && target.w != null) ov.rect = target; else ov.el = target;
    overrides.push(ov); overrides.sort((a, b) => a.t0 - b.t0);
    return ov;
  };

  // ---------- 文字动效 ----------
  const fx = (hz.fx = {});
  const every = hz.every;
  const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;");
  const charsOf = (el, text) => { el.innerHTML = ""; return [...text].map((c) => { const s = mk("span", "hz-ch", el); s.textContent = c; return s; }); };

  // 逐字上浮:模糊变清,逐字错开(A_rise)
  fx.rise = (el, text, t0, o = {}) => {
    el = $(el); const gap = o.gap ?? 0.06, d = o.d ?? 0.8, dy = o.dy ?? 0.32, bl = o.blur ?? 0.09, s0 = o.s0 ?? 1, dx = o.dx ?? 0, e = o.e || EOUT;
    if (o.grad !== false) el.classList.add("hz-grad");
    const cs = charsOf(el, text); mark(el, t0 + (cs.length - 1) * gap + d);
    every((t) => cs.forEach((c, i) => {
      const dt = t - (t0 + i * gap);
      if (dt <= 0) { c.style.opacity = 0; return; }
      const p = ev(e, dt, d), a = Math.pow(clamp(dt / (d * 0.55)), 1.2), b = bl * (1 - clamp(dt / (d * 0.9)));
      c.style.opacity = a;
      c.style.transform = p >= 1 ? "none" : `translate(${dx * (1 - p)}em,${dy * (1 - p)}em) scale(${lerp(s0, 1, p)})`;
      c.style.filter = b > 0.002 ? `blur(${b}em)` : "none";
    }));
    return cs;
  };

  // 光标擦出:竖光标从左滑到右,字随之显现(A_wipe + 光标)
  fx.caret = (el, text, t0, o = {}) => {
    el = $(el); const d = o.d ?? 0.75, e = o.e || EXPO, soft = o.soft ?? 0.12;
    el.innerHTML = ""; el.style.position = el.style.position || "";
    const box = mk("span", "", el, "position:relative;display:inline-block");
    const tx = mk("span", "", box); tx.innerHTML = esc(text);
    if (o.grad) { tx.classList.add("hz-grad", "hz-gradself"); }
    const bar = mk("span", "hz-cbar", box); if (o.color) bar.style.setProperty("--hz-caret", o.color);
    mark(el, t0 + d);
    every((t) => {
      const u = t < t0 ? 0 : ev(e, t - t0, d), edge = u * (1 + soft);
      const m = u >= 1 ? "none" : `linear-gradient(90deg,#000 ${(edge - soft) * 100}%,transparent ${edge * 100}%)`;
      tx.style.webkitMaskImage = m; tx.style.maskImage = m;
      bar.style.left = `calc(${Math.min(1, u) * 100}% + 0.06em)`;
      const tin = clamp((t - t0 + 0.18) / 0.18), tout = 1 - clamp((t - t0 - d - (o.hold ?? 0.25)) / 0.3);
      bar.style.opacity = Math.min(tin, tout);
    });
    return el;
  };

  // 打字:逐字出现 + 闪烁光标;o.delAt 开始删除、o.next 换成新词
  fx.type = (el, text, t0, o = {}) => {
    el = $(el); const gap = o.gap ?? 0.065, dgap = o.delGap ?? 0.035, ngap = o.nextGap ?? gap;
    const A = [...text], B = o.next != null ? [...o.next] : null, tEndA = t0 + A.length * gap;
    const tDel = o.delAt ?? null, tDelEnd = tDel != null ? tDel + A.length * dgap : null, tB = tDelEnd != null ? tDelEnd + (o.pause ?? 0.18) : null;
    const tOff = o.caretOff ?? 1e9;
    mark(el, B && tB != null ? tB + B.length * ngap : tEndA);
    if (o.grad) el.classList.add("hz-grad");
    let last = "";
    every((t) => {
      let chars = A, n, busy;
      if (t < t0) { n = 0; busy = false; }
      else if (tDel == null || t < tDel) { n = Math.min(A.length, Math.floor((t - t0) / gap) + 1); busy = t < tEndA + 0.05; }
      else if (t < tDelEnd) { n = Math.max(0, A.length - Math.floor((t - tDel) / dgap) - 1); busy = true; }
      else if (!B || t < tB) { n = 0; busy = false; chars = B || A; }
      else { chars = B; n = Math.min(B.length, Math.floor((t - tB) / ngap) + 1); busy = t < tB + B.length * ngap + 0.05; }
      const blink = o.caret === false || t >= tOff || t < t0 - 0.25 ? 0 : busy ? 1 : Math.sin(t * 2 * Math.PI * 1.1) > -0.2 ? 1 : 0.0;
      const cls = o.grad ? "hz-ch" : "";
      const key = n + "|" + chars.length + "|" + blink;
      if (key === last) return; last = key;
      const vis = chars.slice(0, n).map((c) => `<span class="${cls}">${esc(c)}</span>`).join("");
      const hid = o.fixed ? `<span style="visibility:hidden">${esc(chars.slice(n).join(""))}</span>` : "";
      el.innerHTML = vis + `<span class="hz-cwrap"><span class="hz-cbar" style="opacity:${blink}"></span></span>` + hid;
    });
    return el;
  };

  // 数字滚动(里程表):每位独立滚,低位连续滚、高位进位时滚;千分位
  fx.odo = (el, value, t0, o = {}) => {
    el = $(el); const d = o.d ?? 1.6, e = o.e || EXPO, sep = o.sep ?? ",", dec = o.decimals ?? 0;
    const scale = Math.pow(10, dec), V = Math.round(value * scale), digits = String(V).padStart(dec + 1, "0"), n = digits.length;
    el.innerHTML = ""; const box = mk("span", "hz-odo", el);
    if (o.grad !== false) el.classList.add("hz-grad");
    if (o.prefix) { const p = mk("span", "hz-ch", box); p.textContent = o.prefix; }
    const cols = [];
    for (let i = 0; i < n; i++) {
      const pos = n - 1 - i - dec; // 整数位序号(0=个位)
      if (i > 0 && dec && i === n - dec) { const s = mk("span", "hz-sep hz-ch", box); s.textContent = "."; }
      else if (i > 0 && sep && pos >= 2 && (pos + 1) % 3 === 0) { const s = mk("span", "hz-sep hz-ch", box); s.textContent = sep; }
      const c = mk("span", "hz-col", box), a = mk("span", "hz-ch", c), b = mk("span", "hz-ch", c);
      cols.push({ p: Math.pow(10, n - 1 - i), a, b, last: "" });
    }
    if (o.suffix) { const s = mk("span", "hz-ch", box); s.textContent = o.suffix; }
    mark(el, t0 + d);
    every((t) => {
      const k = clamp((t - t0 + 0.15) / 0.3);
      box.style.opacity = k; box.style.transform = `translateY(${(1 - EOUT(k)) * 0.15}em)`;
      const v = V * ev(e, Math.max(0, t - t0), d);
      for (const c of cols) {
        const base = Math.floor(v / c.p), fr = c.p === 1 ? v - Math.floor(v) : smooth((v % c.p) - (c.p - 1));
        const d0 = base % 10, d1 = (base + 1) % 10, done = v >= V;
        c.a.textContent = d0; c.b.textContent = d1;
        const f = done ? 0 : fr;
        c.a.style.transform = `translateY(${-f}em)`; c.a.style.opacity = o.zeros || c.p === 1 || base > 0 ? 1 - f * 0.7 : 0; // 前导 0 默认隐藏
        c.b.style.transform = `translateY(${1 - f}em)`; c.b.style.opacity = f;
      }
    });
    return el;
  };

  // 荧光笔:字下(under)或字后(behind)一道笔触从左到右刷出。el 是已有的文字元素
  fx.hl = (el, t0, o = {}) => {
    el = $(el); const d = o.d ?? 0.55, e = o.e || EOUT, mode = o.mode || "behind", c = o.color || "var(--c-main)";
    let host = el;
    if (!el.classList.contains("hz-hlw")) { const kids = [...el.childNodes]; host = mk("span", "hz-hlw", el); kids.forEach((k) => host.appendChild(k)); }
    else host = el;
    const s = mk("span", "hz-stroke", host);
    if (mode === "under") { s.style.cssText += `bottom:-0.06em;height:${o.h ?? 0.12}em;background:${c};opacity:${o.a ?? 0.95}`; }
    else { s.style.cssText += `bottom:${o.lift ?? 0.04}em;height:${o.h ?? 0.46}em;background:linear-gradient(90deg,color-mix(in srgb,${c} 75%,transparent),${c} 30%,${c} 85%,color-mix(in srgb,${c} 80%,transparent));opacity:${o.a ?? 0.42}`; }
    every((t) => {
      const u = t < t0 ? 0 : ev(e, t - t0, d);
      s.style.width = `calc(${u} * (100% + 0.16em))`; s.style.display = u <= 0 ? "none" : "";
    });
    // 被 fx.rise 等改写过的元素,它的 data-t0 仍有效;荧光笔本身不改 t0
    return s;
  };

  // 胶囊标签弹出(弹簧):o.color 主色(点和描边),o.dot=false 去掉圆点
  fx.pill = (el, text, t0, o = {}) => {
    el = $(el); const sp = o.e || hz.spring(o.resp ?? 0.5, o.damp ?? 0.62), s0 = o.s0 ?? 0.6;
    el.innerHTML = ""; const p = mk("span", "hz-pill", el);
    if (o.color) p.style.setProperty("--hz-pc", o.color);
    if (o.dot !== false) mk("i", "", p);
    const tx = mk("span", "", p); tx.textContent = text;
    mark(el, t0 + 0.35);
    every((t) => {
      const dt = t - t0;
      if (dt <= 0) { p.style.opacity = 0; return; }
      const s = lerp(s0, 1, sp.spring ? sp.f(dt) : sp(clamp(dt / 0.6)));
      p.style.opacity = clamp(dt / 0.16); p.style.transform = `scale(${s})`;
      const b = 0.12 * (1 - clamp(dt / 0.3)); p.style.filter = b > 0.002 ? `blur(${b}em)` : "none";
    });
    return el;
  };

  // 全大写字距拉开的小标签;o.anim = "wipe"(默认,从左擦出)/ "rise" / "fade"
  fx.caps = (el, text, t0, o = {}) => {
    el = $(el); el.classList.add("hz-caps"); if (o.track) el.style.setProperty("--hz-track", o.track + "em");
    if (o.color) el.style.color = o.color;
    const anim = o.anim || "wipe", d = o.d ?? 0.6;
    if (anim === "rise") { el.classList.remove("hz-grad"); return fx.rise(el, text.toUpperCase(), t0, Object.assign({ gap: 0.02, d: 0.6, grad: false }, o)); }
    el.textContent = text.toUpperCase(); mark(el, t0 + d);
    every((t) => {
      if (anim === "fade") { el.style.opacity = clamp((t - t0) / d); return; }
      const u = t < t0 ? 0 : ev(o.e || EXPO, t - t0, d), soft = 0.18, edge = u * (1 + soft);
      const m = u >= 1 ? "none" : `linear-gradient(90deg,#000 ${(edge - soft) * 100}%,transparent ${edge * 100}%)`;
      el.style.webkitMaskImage = m; el.style.maskImage = m;
    });
    return el;
  };
})();
