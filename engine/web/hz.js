/* hz.js —— 网页场景运行时:一切画面都由 seek(t) 按时间「定格」,浏览器负责 3D 透视、模糊、阴影等真实渲染。
   用法见 engine/WEB.md。 */
(function () {
  const hz = (window.hz = {});
  const $ = (s) => (typeof s === "string" ? document.querySelector(s) : s);
  hz.$ = $;
  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  hz.clamp = clamp;
  hz.lerp = (a, b, u) => a + (b - a) * u;

  // ---------- 缓动 ----------
  function bez(x1, y1, x2, y2) {
    const cx = 3 * x1, bx = 3 * (x2 - x1) - cx, ax = 1 - cx - bx;
    const cy = 3 * y1, by = 3 * (y2 - y1) - cy, ay = 1 - cy - by;
    const sx = (t) => ((ax * t + bx) * t + cx) * t, sy = (t) => ((ay * t + by) * t + cy) * t;
    const dx = (t) => (3 * ax * t + 2 * bx) * t + cx;
    return (x) => {
      if (x <= 0) return 0; if (x >= 1) return 1;
      let t = x;
      for (let i = 0; i < 8; i++) { const e = sx(t) - x; const d = dx(t); if (Math.abs(e) < 1e-6 || Math.abs(d) < 1e-6) break; t -= e / d; }
      return sy(clamp(t));
    };
  }
  hz.bez = bez;
  hz.ease = {
    out: bez(0.16, 1, 0.3, 1),      // 快起慢停(expo out)
    inout: bez(0.65, 0, 0.35, 1),   // 两头慢
    soft: bez(0.25, 0.1, 0.25, 1),  // 苹果默认 ease
    in: bez(0.55, 0, 0.75, 0.05),
    lin: (x) => x,
  };
  // 弹簧(按真实秒数,不按段长):resp=响应时间(秒),damp=阻尼(1 不回弹,0.7 轻弹,0.5 明显弹)
  hz.spring = (resp = 0.5, damp = 0.82) => {
    const w = (2 * Math.PI) / resp, z = damp;
    const f = (t) => {
      if (t <= 0) return 0;
      if (z < 1) { const wd = w * Math.sqrt(1 - z * z); return 1 - Math.exp(-z * w * t) * (Math.cos(wd * t) + ((z * w) / wd) * Math.sin(wd * t)); }
      return 1 - Math.exp(-w * t) * (1 + w * t);
    };
    return { spring: true, f };
  };

  // ---------- 关键帧轨道 ----------
  const KNOWN = ["x", "y", "z", "rx", "ry", "rz", "s", "sx", "sy", "o", "blur"];
  const DEF = { x: 0, y: 0, z: 0, rx: 0, ry: 0, rz: 0, s: 1, sx: 1, sy: 1, o: 1, blur: 0 };
  const tracks = [], hooks = [], scenes = [], states = [];
  hz.track = (el, keys) => {
    el = $(el); keys = keys.slice().sort((a, b) => a.t - b.t);
    const props = new Set(); keys.forEach((k) => Object.keys(k).forEach((p) => p !== "t" && p !== "e" && props.add(p)));
    tracks.push({ el, keys, props: [...props] });
    return el;
  };
  function val(keys, p, t) {
    let prev = null, next = null;
    for (const k of keys) { if (!(p in k)) continue; if (k.t <= t) prev = k; else { next = k; break; } }
    if (!prev) return next[p];
    if (!next) return prev[p];
    const e = next.e || hz.ease.out;
    const u = e.spring ? e.f(t - prev.t) : e(clamp((t - prev.t) / (next.t - prev.t)));
    return prev[p] + (next[p] - prev[p]) * u;
  }
  hz.val = val;
  function applyTrack(tr, t) {
    const v = Object.assign({}, DEF);
    for (const p of tr.props) v[p] = val(tr.keys, p, t);
    const st = tr.el.style;
    const has = (p) => tr.props.includes(p);
    if (["x", "y", "z", "rx", "ry", "rz", "s", "sx", "sy"].some(has)) {
      const c = tr.el.dataset.anchor === "tl" ? "" : "translate(-50%,-50%) ";
      st.transform = `${c}translate3d(${v.x}px,${v.y}px,${v.z}px) rotateX(${v.rx}deg) rotateY(${v.ry}deg) rotateZ(${v.rz}deg) scale(${v.s * v.sx},${v.s * v.sy})`;
    }
    if (has("o")) st.opacity = clamp(v.o);
    if (has("blur")) st.filter = v.blur > 0.05 ? `blur(${v.blur}px)` : "none";
    for (const p of tr.props) if (!KNOWN.includes(p)) st.setProperty("--" + p, v[p]);
  }

  // ---------- 其它时间驱动 ----------
  hz.every = (fn) => hooks.push(fn);                    // fn(t) 每帧调用
  hz.scene = (el, t0, t1) => { el = $(el); scenes.push({ el, t0, t1 }); el.dataset.t0 = t0; return el; };
  // 打字:逐字出现,光标闪
  hz.type = (el, text, t0, cps = 14, caret = true, t1 = 1e9) => {
    el = $(el);
    hz.every((t) => {
      if (t < t0) return;
      const n = clamp(Math.floor((t - t0) * cps), 0, [...text].length);
      const blink = caret && t < t1 && (t < t0 + [...text].length / cps + 0.1 || Math.floor(t * 2) % 2 === 0);
      el.innerHTML = [...text].slice(0, n).join("").replace(/</g, "&lt;") + (blink ? '<span class="caret"></span>' : "");
    });
  };
  // 数字滚动
  hz.count = (el, a, b, t0, t1, fmt = (v) => Math.round(v).toLocaleString("en-US"), e = hz.ease.out) => {
    el = $(el); hz.every((t) => { el.textContent = fmt(a + (b - a) * e(clamp((t - t0) / (t1 - t0)))); });
  };
  // 状态类:在 [tOn, tOff) 内给元素加 cls(可在 iframe 组件里,用来触发 .hz-h 悬停 / .hz-a 按下 / 自定义类)
  hz.state = (frame, sel, cls, tOn, tOff = 1e9) => states.push({ frame: $(frame), sel, cls, tOn, tOff, kind: "class" });
  hz.check = (frame, sel, tOn, tOff = 1e9) => states.push({ frame: $(frame), sel, tOn, tOff, kind: "check" });

  // 圆形揭开转场(用 mask;不要用 clip-path,无界面 Chrome 截图会出透明洞)
  hz.circleReveal = (el, cx, cy, t0, dur = 0.6, r1 = 2300, e = hz.ease.inout) => {
    el = $(el);
    hz.every((t) => {
      const u = e(clamp((t - t0) / dur));
      const m = u >= 1 ? "none" : `radial-gradient(circle ${Math.max(0.1, u * r1)}px at ${cx}px ${cy}px, #000 99.5%, transparent 100%)`;
      el.style.webkitMaskImage = m; el.style.maskImage = m;
    });
  };


  // ---------- 逐字拆分:返回每个字的 span,配合 hz.track 做逐字动画 ----------
  hz.chars = (el, text) => { el = $(el); el.innerHTML = ""; return [...text].map((c) => { const s = document.createElement("span"); s.className = "ch"; s.textContent = c; el.appendChild(s); return s; }); };
  // 逐字上浮(带模糊变清)
  hz.riseChars = (el, text, t0, gap = 0.07, o = {}) => {
    const cs = hz.chars(el, text);
    cs.forEach((c, i) => { c.dataset.anchor = "tl"; const t = t0 + i * gap;
      hz.track(c, [{ t, o: 0, y: o.dy ?? 60, blur: o.blur ?? 14, s: o.s0 ?? 1 }, { t: t + (o.d ?? 0.7), o: 1, y: 0, blur: 0, s: 1, e: o.e || hz.ease.out }]); });
    return cs;
  };
  // 从左到右擦出(mask),可带一根光标竖条:caret = 光标元素
  hz.wipe = (el, t0, d = 0.6, o = {}) => {
    el = $(el);
    hz.every((t) => {
      const u = (o.e || hz.ease.out)(clamp((t - t0) / d)), soft = o.soft ?? 6;
      const m = u >= 1 ? "none" : `linear-gradient(90deg, #000 ${u * 100 - soft}%, transparent ${u * 100}%)`;
      el.style.webkitMaskImage = m; el.style.maskImage = m;
      if (o.caret) { const c = $(o.caret); c.style.left = `calc(${u * 100}% + 6px)`; c.style.opacity = t < t0 ? 0 : t > t0 + d + 0.25 ? 0 : 1; }
    });
  };
  // 画线(SVG path,pathLength=1)
  hz.draw = (path, t0, d = 0.6, e = hz.ease.out) => { path = $(path); path.setAttribute("pathLength", "1"); path.style.strokeDasharray = "1";
    hz.every((t) => { path.style.strokeDashoffset = 1 - e(clamp((t - t0) / d)); }); };

  // ---------- 无限画布:镜头在节点之间飞行,离开的节点虚化压暗后退 ----------
  // nodes: [{el, x, y, t(到位时刻), zoom=1, flight=0.75, pre=0.6, drift=0.012, keys:[{t, x, y, zoom}]}]
  const FLY = bez(0.55, 0, 0.12, 1);   // 镜头飞行:起步柔、落位稳
  hz.infinite = (world, nodes, o = {}) => {
    world = $(world);
    const W = o.W || 1920, H = o.H || 1080, dip = o.dip ?? 0.16;
    nodes.forEach((n) => { n.el.style.left = n.x + "px"; n.el.style.top = n.y + "px"; n.zoom = n.zoom || 1; n.flight = n.flight ?? 0.75; n.pre = n.pre ?? 0.6; n.drift = n.drift ?? 0.012; });
    const start = (n) => n.t - n.flight * n.pre;
    const camAt = (n, t) => {   // 节点到位后的镜头(漂移 + 段内推镜)
      let x = n.x, y = n.y, z = n.zoom;
      if (n.keys) for (const k of n.keys) { const u = hz.ease.inout(clamp((t - k.t0) / (k.t1 - k.t0))); x += (k.x || 0) * u; y += (k.y || 0) * u; z *= 1 + ((k.zoom || 1) - 1) * u; }
      z *= 1 + n.drift * Math.max(0, t - n.t);
      return [x, y, z];
    };
    hz.cam = { x: 0, y: 0, z: 1 };
    hz.every((t) => {
      let i = 0; for (let j = 0; j < nodes.length; j++) if (start(nodes[j]) <= t) i = j;
      const b = nodes[i]; let [x, y, z] = camAt(b, t);
      if (i > 0 && t < start(b) + b.flight) {
        const a = nodes[i - 1], [ax, ay, az] = camAt(a, start(b)), u = clamp((t - start(b)) / b.flight), e = FLY(u);
        x = ax + (x - ax) * e; y = ay + (y - ay) * e; z = Math.exp(Math.log(az) + (Math.log(z) - Math.log(az)) * e) * (1 - dip * Math.sin(Math.PI * Math.min(1, u * 1.15)));
      }
      hz.cam = { x, y, z, i };
      world.style.transform = `translate(${W / 2}px,${H / 2}px) scale(${z}) translate(${-x}px,${-y}px)`;
      nodes.forEach((n, j) => {
        const leave = nodes[j + 1] ? start(nodes[j + 1]) : 1e9;
        const k = clamp((t - leave) / 0.7), k2 = nodes[j + 2] ? clamp((t - start(nodes[j + 2])) / 0.8) : 0;
        const vis = t >= start(n) - 1.2 && k2 < 1 || (j <= i && j >= i - 2);
        n.el.style.display = vis ? "" : "none";
        if (!vis) return;
        const f = n.fade ?? 1, blur = (k * 10 + k2 * 8) * f, br = 1 - (0.5 * k + 0.25 * k2) * f;
        n.el.style.filter = blur > 0.05 ? `blur(${blur}px) brightness(${br}) saturate(${1 - 0.4 * k})` : "none";
        n.el.style.opacity = 1 - k2;
      });
    });
  };

  // ---------- 电影感深色背景:径向渐变 + 视差点阵 + 斜向光 + 颗粒 + 暗角 ----------
  hz.cinemaBg = (parent, o = {}) => {
    parent = $(parent);
    const mk = (css) => { const d = document.createElement("div"); d.style.cssText = "position:absolute;inset:0;pointer-events:none;" + css; parent.appendChild(d); return d; };
    mk(`background:radial-gradient(120% 90% at 50% 45%, ${o.c0 || "#3a3438"} 0%, ${o.c1 || "#1d1a1d"} 60%, ${o.c2 || "#121012"} 100%)`);
    const dots = mk(`background-image:radial-gradient(rgba(255,240,225,.07) 1.4px, transparent 1.6px);background-size:44px 44px;`);
    const beam = mk(`background:linear-gradient(115deg, transparent 35%, rgba(255,235,210,.035) 45%, transparent 55%);background-size:300% 100%;`);
    const cv = document.createElement("canvas"); cv.width = cv.height = 256; const g = cv.getContext("2d"), im = g.createImageData(256, 256);
    let seed = 7; const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
    for (let i = 0; i < im.data.length; i += 4) { const v = rnd() * 255; im.data[i] = im.data[i + 1] = im.data[i + 2] = v; im.data[i + 3] = 255; }
    g.putImageData(im, 0, 0);
    const grain = mk(`background-image:url(${cv.toDataURL()});opacity:${o.grain ?? 0.05};mix-blend-mode:overlay;z-index:90`);
    mk(`background:radial-gradient(130% 100% at 50% 50%, transparent 55%, rgba(0,0,0,.55) 100%);z-index:91`);
    hz.every((t) => {
      const c = hz.cam || { x: 0, y: 0, z: 1 };
      dots.style.backgroundPosition = `${-c.x * 0.3 * c.z}px ${-c.y * 0.3 * c.z}px`; dots.style.backgroundSize = `${44 * (0.7 + 0.3 * c.z)}px ${44 * (0.7 + 0.3 * c.z)}px`;
      beam.style.backgroundPosition = `${(t * 3) % 300}% 0`;
      const f = Math.floor(t * 24); grain.style.backgroundPosition = `${(f * 97) % 256}px ${(f * 61) % 256}px`;
    });
  };

  // ---------- uiverse 组件 ----------
  const frames = [];
  hz.ui = (id, o = {}) => {
    const c = window.UIVERSE[id]; if (!c) throw new Error("没有打包组件 #" + id);
    const f = document.createElement("iframe");
    const z = o.zoom || 1, bg = o.bg || "transparent";
    f.className = "ui " + (o.cls || "");
    f.style.width = (o.w || 360) + "px"; f.style.height = (o.h || 240) + "px";
    f.setAttribute("scrolling", "no");
    f.srcdoc = `<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;height:100%;background:${bg};overflow:hidden}
      body{display:flex;align-items:center;justify-content:center}#hzw{transform:scale(${z});transform-origin:center}
      *{transition-delay:0s}</style></head><body><div id="hzw">${c.html}</div></body></html>`;
    f.dataset.uid = id; f.dataset.author = c.author;
    frames.push(f);
    if (o.parent) $(o.parent).appendChild(f);
    return f;
  };

  // ---------- 动画同步(CSS @keyframes / transition 也按时间定格) ----------
  const startOf = new WeakMap();
  function baseT0(node, doc) {
    let el = node && node.nodeType === 1 ? node : null;
    while (el) { if (el.dataset && el.dataset.t0 !== undefined) return +el.dataset.t0; el = el.parentElement; }
    const fe = doc.defaultView && doc.defaultView.frameElement;
    return fe ? baseT0(fe, fe.ownerDocument) : 0;
  }
  function sync(doc, t) {
    for (const a of doc.getAnimations()) {
      let st = startOf.get(a);
      if (st === undefined) {
        if (typeof CSSTransition !== "undefined" && a instanceof CSSTransition) st = doc.__hzToggle != null ? doc.__hzToggle : t;
        else st = baseT0(a.effect && a.effect.target, doc);
        startOf.set(a, st);
      }
      a.pause();
      a.currentTime = Math.max(0, t - st) * 1000;
    }
  }

  // ---------- seek ----------
  const HZ = (window.HZ = window.HZ || {});
  HZ.ready = false;
  HZ.seek = async (t) => {
    HZ.t = t;
    for (const s of scenes) s.el.style.display = t >= s.t0 && t < s.t1 ? "" : "none";
    for (const tr of tracks) applyTrack(tr, t);
    for (const h of hooks) h(t);
    for (const s of states) {
      const doc = s.frame.tagName === "IFRAME" ? s.frame.contentDocument : document;
      const on = t >= s.tOn && t < s.tOff;
      const els = s.sel ? doc.querySelectorAll(s.sel) : [s.frame];
      els.forEach((el) => {
        const cur = s.kind === "check" ? el.checked : el.classList.contains(s.cls);
        if (cur !== on) {
          doc.__hzToggle = on ? s.tOn : s.tOff;
          if (s.kind === "check") el.checked = on; else el.classList.toggle(s.cls, on);
        }
      });
    }
    // 先让样式生效,再同步动画
    document.body.offsetHeight;
    sync(document, t);
    for (const f of frames) if (f.contentDocument && f.isConnected) { f.contentDocument.body && f.contentDocument.body.offsetHeight; sync(f.contentDocument, t); }
  };
  hz.start = async (dur) => {
    HZ.dur = dur;
    await document.fonts.ready;
    await Promise.all(frames.map((f) => new Promise((r) => {
      if (f.contentDocument && f.contentDocument.readyState === "complete" && f.contentDocument.body && f.contentDocument.body.childElementCount) r();
      else { f.addEventListener("load", r, { once: true }); setTimeout(r, 4000); }
    })));
    await HZ.seek(0);
    HZ.ready = true;
  };
  // 预览:浏览器直接打开页面时按真实时间播放(?play)
  if (location.search.includes("play")) {
    window.addEventListener("load", () => { const t0 = performance.now(); const loop = () => { HZ.ready && HZ.seek(((performance.now() - t0) / 1000) % HZ.dur); requestAnimationFrame(loop); }; loop(); });
  }
})();
