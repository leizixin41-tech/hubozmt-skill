/* hz_ui3d.js —— 3D 衔接(卡片立起/放平)+ UI 交互小部件 hz.w.*。在 hz.js 之后加载。说明见 engine/web/UI3D.md。
   颜色全部取 CSS 变量:--c-bg --c-ink --c-mute --c-main --c-accent --c-warn --c-card --c-line(可选 --c-on-main 按钮字色)。
   所有动画都按绝对时间 t 计算(纯函数),交给 hz.every 每帧调用。 */
(function () {
  const hz = window.hz; if (!hz) throw new Error("hz_ui3d.js 必须在 hz.js 之后加载");
  const E = hz.ease, clamp = hz.clamp, lerp = hz.lerp;
  const seg = (t, t0, d, e = E.out) => e(clamp((t - t0) / d));
  const spr = (t, t0, sp) => (t <= t0 ? 0 : sp.f(t - t0));
  const bump = (u) => (u <= 0 || u >= 1 ? 0 : Math.sin(Math.PI * u));
  const MOVE = hz.bez(0.5, 0, 0.15, 1);   // 鼠标/滑块移动:起步柔、到位稳
  const SVGNS = "http://www.w3.org/2000/svg";
  function mk(tag, cls, parent, html) {
    const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html;
    if (parent) hz.$(parent).appendChild(e); return e;
  }
  const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;");
  // 绝对定位:o.x/o.y 给了就放到父元素里的 (x,y)(左上角),否则按文档流排
  function place(el, o) { if (o.x != null || o.y != null) { el.style.position = "absolute"; el.style.left = (o.x || 0) + "px"; el.style.top = (o.y || 0) + "px"; } if (o.w) el.style.width = o.w + "px"; }
  // 出现:淡入 + 上浮 + 模糊变清(只动根元素的 opacity/translate/filter)
  function appear(el, t0, o = {}) {
    if (t0 == null) return;
    const d = o.d ?? 0.55, dy = o.dy ?? 14, bl = o.blur ?? 6;
    hz.every((t) => {
      const u = seg(t, t0, d);
      el.style.opacity = u; el.style.translate = `0 ${(1 - u) * dy}px`;
      el.style.filter = u < 1 && bl ? `blur(${(1 - u) * bl}px)` : "";
    });
  }

  // ======================= 样式(全部基于 CSS 变量) =======================
  const CSS = `
:root{--hz-card:var(--c-card,color-mix(in srgb,var(--c-bg) 88%,var(--c-ink)));--hz-line:var(--c-line,color-mix(in srgb,var(--c-ink) 12%,transparent));
  --hz-shadow:color-mix(in srgb,var(--c-bg) 35%,black);--hz-on-main:var(--c-on-main,var(--c-ink))}
.hz-card{position:absolute;border-radius:28px;background:color-mix(in srgb,var(--hz-card) 86%,transparent);
  border:1px solid var(--hz-line);overflow:hidden;isolation:isolate;
  backdrop-filter:blur(calc(10px + var(--lift,0) * 18px)) saturate(1.3);-webkit-backdrop-filter:blur(calc(10px + var(--lift,0) * 18px)) saturate(1.3);
  box-shadow:inset 0 1px 0 color-mix(in srgb,var(--c-ink) 10%,transparent),
    0 calc(2px + var(--lift,0) * 50px) calc(8px + var(--lift,0) * 110px) calc(var(--lift,0) * -24px) color-mix(in srgb,var(--hz-shadow) calc(55% + var(--lift,0) * 30%),transparent),
    0 calc(1px + var(--lift,0) * 8px) calc(2px + var(--lift,0) * 18px) color-mix(in srgb,var(--hz-shadow) 40%,transparent)}
.hz-card::after{content:"";position:absolute;inset:0;pointer-events:none;border-radius:inherit;z-index:20;
  background:linear-gradient(calc(120deg + var(--ry,0) * 2deg),transparent 30%,color-mix(in srgb,var(--c-ink) calc(2% + var(--lift,0) * 5%),transparent) 48%,transparent 62%);
  background-size:220% 220%;background-position:calc(50% + var(--ry,0) * 4%) calc(50% + var(--rx,0) * 4%)}
.hz-card-hd{display:flex;align-items:center;gap:12px;padding:22px 28px 0}
.hz-card-hd .t{font:600 24px/1.2 Inter,"Noto Sans SC";color:var(--c-ink);letter-spacing:-.2px}
.hz-card-hd .s{font:500 16px/1.2 Inter,"Noto Sans SC";color:var(--c-mute);margin-left:auto}
.hz-card-bd{position:relative;display:flex;flex-direction:column;gap:18px;padding:22px 28px 28px}
.hz-dim{position:absolute;left:-60000px;top:-60000px;width:120000px;height:120000px;pointer-events:none;background:var(--c-bg);opacity:0}
.hz-ico{display:inline-flex;align-items:center;justify-content:center;flex:none;border-radius:50%}
.hz-ico svg{display:block;overflow:visible}
/* 输入框 */
.hz-w-field{display:flex;flex-direction:column;gap:10px}
.hz-w-field .lb{font:500 16px/1 Inter,"Noto Sans SC";color:var(--c-mute);letter-spacing:.2px}
.hz-w-field .box{position:relative;height:64px;border-radius:16px;display:flex;align-items:center;padding:0 22px;gap:12px;
  background:color-mix(in srgb,var(--c-ink) calc(4% + var(--f,0) * 2%),transparent);border:1px solid var(--hz-line);
  box-shadow:inset 0 0 0 calc(var(--f,0) * 1.5px) var(--c-main),0 0 0 calc(var(--f,0) * 5px) color-mix(in srgb,var(--c-main) 22%,transparent)}
.hz-w-field .v{font:500 27px/1 Inter,"Noto Sans SC";color:var(--c-ink);white-space:pre;font-variant-numeric:tabular-nums;letter-spacing:.3px}
.hz-w-field .ph{position:absolute;left:22px;font:400 25px/1 Inter,"Noto Sans SC";color:var(--c-mute);white-space:nowrap}
.hz-w-field .cr,.hz-w-term .cr{display:inline-block;width:2.5px;height:30px;border-radius:2px;background:var(--c-main);vertical-align:middle;margin-left:2px}
.hz-w-field .ch{display:inline-block;white-space:pre}
/* 按钮 */
.hz-w-btn{display:flex}
.hz-w-btn .face{position:relative;flex:1;height:64px;border-radius:16px;display:flex;align-items:center;justify-content:center;gap:10px;overflow:hidden;
  background:var(--c-main);background-image:linear-gradient(180deg,color-mix(in srgb,var(--c-ink) 16%,transparent),transparent 60%);
  font:600 24px/1 Inter,"Noto Sans SC";color:var(--hz-on-main);letter-spacing:.2px;
  box-shadow:inset 0 1px 0 color-mix(in srgb,var(--c-ink) 28%,transparent),0 calc(14px - var(--p,0) * 10px) calc(30px - var(--p,0) * 18px) -12px color-mix(in srgb,var(--c-main) 70%,transparent)}
.hz-w-btn .rp{position:absolute;width:40px;height:40px;margin:-20px 0 0 -20px;border-radius:50%;background:color-mix(in srgb,var(--hz-on-main) 40%,transparent);opacity:0;pointer-events:none}
.hz-w-btn .lbl{position:relative;display:inline-flex;align-items:center;gap:10px;white-space:nowrap}
/* 转圈 */
.hz-w-spin{display:inline-flex;align-items:center;gap:14px}
.hz-w-spin .tx{font:500 20px/1 Inter,"Noto Sans SC";color:var(--c-mute);white-space:nowrap}
/* 结果行 */
.hz-w-rows{display:flex;flex-direction:column}
.hz-w-row{display:flex;align-items:center;gap:16px;padding:15px 2px;border-top:1px solid var(--hz-line)}
.hz-w-row:first-child{border-top:0}
.hz-w-row .k{font:500 19px/1 Inter,"Noto Sans SC";color:var(--c-mute);white-space:nowrap}
.hz-w-row .v{margin-left:auto;font:600 22px/1 Inter,"Noto Sans SC";color:var(--c-ink);white-space:nowrap;font-variant-numeric:tabular-nums}
/* 列表/网格 */
.hz-w-list{display:grid;gap:12px}
.hz-w-item{position:relative;display:flex;align-items:center;gap:12px;padding:14px 16px;border-radius:14px;
  background:color-mix(in srgb,var(--c-main) calc(var(--on,0) * 14%),color-mix(in srgb,var(--c-ink) 4%,transparent));
  border:1px solid color-mix(in srgb,var(--c-main) calc(var(--on,0) * 55%),var(--hz-line))}
.hz-w-item .lb{font:500 19px/1.1 Inter,"Noto Sans SC";color:var(--c-ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hz-w-item .tag{margin-left:auto;font:500 14px/1 Inter,"Noto Sans SC";color:var(--c-mute);white-space:nowrap}
/* 终端 */
.hz-w-term{border-radius:18px;overflow:hidden;background:color-mix(in srgb,var(--c-bg) 82%,black);border:1px solid var(--hz-line);
  box-shadow:inset 0 1px 0 color-mix(in srgb,var(--c-ink) 8%,transparent)}
.hz-w-term .hd{height:44px;display:flex;align-items:center;gap:8px;padding:0 16px;border-bottom:1px solid var(--hz-line)}
.hz-w-term .hd i{width:12px;height:12px;border-radius:50%;display:block}
.hz-w-term .hd .tt{margin-left:10px;font:500 15px/1 Inter;color:var(--c-mute)}
.hz-w-term .bd{position:relative;overflow:hidden;padding:0 20px;-webkit-mask-image:linear-gradient(transparent 0,#000 18px);mask-image:linear-gradient(transparent 0,#000 18px)}
.hz-w-term .sc{position:relative;padding:16px 0}
.hz-w-term .ln{font:400 19px/1.65 "JetBrains Mono",monospace;color:var(--c-mute);white-space:pre;height:calc(19px * 1.65)}
.hz-w-term .ln .pr{color:var(--c-main)} .hz-w-term .ln .cm{color:var(--c-ink)} .hz-w-term .ln.ok{color:var(--c-accent)} .hz-w-term .ln.er{color:var(--c-warn)}
.hz-w-term .cr{height:22px;width:11px;border-radius:2px;margin-left:1px;vertical-align:-4px}
/* 进度条 */
.hz-w-prog{display:flex;flex-direction:column;gap:10px}
.hz-w-prog .top{display:flex;align-items:baseline}
.hz-w-prog .lb{font:500 18px/1 Inter,"Noto Sans SC";color:var(--c-mute)}
.hz-w-prog .pc{margin-left:auto;font:600 20px/1 "JetBrains Mono",monospace;color:var(--c-ink)}
.hz-w-prog .tr{position:relative;height:10px;border-radius:99px;background:color-mix(in srgb,var(--c-ink) 9%,transparent);overflow:hidden}
.hz-w-prog .fl{position:absolute;overflow:hidden;left:0;top:0;bottom:0;border-radius:99px;background:linear-gradient(90deg,var(--c-main),var(--c-accent))}
.hz-w-prog .sh{position:absolute;top:0;bottom:0;width:120px;background:linear-gradient(90deg,transparent,color-mix(in srgb,var(--c-ink) 35%,transparent),transparent)}
/* 鼠标 */
.hz-w-cursor{position:absolute;left:0;top:0;width:0;height:0;z-index:60;pointer-events:none}
.hz-w-cursor svg{position:absolute;left:-5px;top:-3px;overflow:visible;filter:drop-shadow(0 4px 6px color-mix(in srgb,var(--hz-shadow) 70%,transparent))}
.hz-w-cursor .ring{position:absolute;width:44px;height:44px;margin:-22px 0 0 -22px;border-radius:50%;border:2.5px solid var(--c-main);opacity:0}
`;
  const st = document.createElement("style"); st.id = "hz-ui3d-css"; st.textContent = CSS; document.head.appendChild(st);

  // ======================= 图标 =======================
  function icoCheck(parent, size, bg, fg) {     // 圆底勾,返回 {el, path}
    const el = mk("span", "hz-ico", parent); el.style.width = el.style.height = size + "px"; el.style.background = bg;
    el.innerHTML = `<svg width="${size * 0.56}" height="${size * 0.56}" viewBox="0 0 24 24"><path d="M5 12.5 L10 17 L19 7.5" fill="none" stroke="${fg}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"/></svg>`;
    return { el, path: el.querySelector("path") };
  }

  // ======================= 卡片 =======================
  // hz.card(parent, {w, h, x, y, title, sub, t0}) → 卡片根元素(.hz-card);内容放 card.body
  hz.card = (parent, o = {}) => {
    const c = mk("div", "hz-card", parent);
    c.style.width = (o.w || 640) + "px"; if (o.h) c.style.height = o.h + "px";
    if (o.x != null) c.style.left = o.x + "px"; if (o.y != null) c.style.top = o.y + "px";
    if (o.center) { c.style.marginLeft = -(o.w || 640) / 2 + "px"; if (o.h) c.style.marginTop = -o.h / 2 + "px"; }
    c.dataset.t0 = o.t0 ?? 0;
    if (o.title || o.sub) {
      const hd = mk("div", "hz-card-hd", c);
      if (o.icon) hd.appendChild(typeof o.icon === "string" ? mk("span", "", null, o.icon) : o.icon);
      if (o.title) mk("div", "t hz-txt", hd, esc(o.title));
      if (o.sub) mk("div", "s hz-txt", hd, esc(o.sub));
    }
    c.body = mk("div", "hz-card-bd", c);
    appear(c, o.appear, { dy: 30, blur: 10, d: 0.7 });
    return c;
  };

  // ======================= 3D 衔接 =======================
  const ctls = new WeakMap();
  function ctl(card) {
    let c = ctls.get(card); if (c) return c;
    card.classList.add("hz-card");
    c = { segs: [], base: card.style.transform || "", z0: card.style.zIndex, dim: null, anc: [], persp: null };
    ctls.set(card, c);
    // 压暗层一开始就建好(不在播放途中插 DOM,免得排版检查按 DOM 路径追踪文字时把卡片里的字当成「消失」)
    if (card.parentElement) { c.dim = mk("div", "hz-dim"); card.parentElement.insertBefore(c.dim, card); c.dim.style.zIndex = 999; }
    hz.every((t) => drive(card, c, t));
    return c;
  }
  const DIVE = { fill: 0.8, rx: 7, ry: -9, rz: 0, ox: 0, oy: 0, dim: 0.42, dimBlur: 3, drift: 1.4, persp: 1700, lead: 0.1,
    spring: [0.78, 0.84], tilt: [0.95, 0.68], peel: 16, cam: false };
  const SETTLE = { spring: [0.7, 0.86], tilt: [0.75, 0.8], peel: -6, cam: false };
  // 计算到 t 时刻的状态:p=位移缩放进度(0 平放原位 → 1 立起居中),rx/ry 角度,lift 层次
  function stateAt(c, t) {
    let s = { p: 0, rx: 0, ry: 0, rz: 0, lift: 0, o: DIVE, sq: 0 };
    for (const g of c.segs) {
      if (t < g.t0) break;
      const S = stateAt0(c, g);
      const o = g.o, dt = t - g.t0 - (g.type === "dive" ? o.lead : 0);
      const sp = hz.spring(o.spring[0], o.spring[1]), tl = hz.spring(o.tilt[0], o.tilt[1]);
      const P = dt <= 0 ? 0 : sp.f(dt), R = dt <= 0 ? 0 : tl.f(dt);
      const T = g.type === "dive" ? { p: 1, rx: o.rx, ry: o.ry, rz: o.rz, lift: 1 } : { p: 0, rx: 0, ry: 0, rz: 0, lift: 0 };
      const pk = bump(clamp(dt / (o.spring[0] * 0.9))) * o.peel;      // 立起时先多仰一点再回到目标角(翻起来的感觉)
      // 起手预备:dive 先轻按下 2.5%,settle 落地时轻压一下
      const sq = g.type === "dive" ? bump(clamp((t - g.t0) / 0.2)) * 0.025 : bump(clamp((dt - o.spring[0] * 0.55) / 0.3)) * 0.012;
      s = { p: lerp(S.p, T.p, P), rx: lerp(S.rx, T.rx, R) + pk, ry: lerp(S.ry, T.ry, R) - pk * 0.35, rz: lerp(S.rz, T.rz, R),
        lift: lerp(S.lift, T.lift, g.type === "dive" ? seg(dt, 0, 0.6) : clamp(P)), o: g.type === "dive" ? o : S.o, sq };
    }
    return s;
  }
  function stateAt0(c, g) {   // 段起点的状态(用前面的段算),缓存
    if (g.S) return g.S;
    const i = c.segs.indexOf(g);
    g.S = i === 0 ? { p: 0, rx: 0, ry: 0, rz: 0, lift: 0, o: DIVE } : stateAt({ segs: c.segs.slice(0, i) }, g.t0 - 1e-6);
    return g.S;
  }
  function drive(card, c, t) {
    const s = stateAt(c, t), o = s.o;
    const active = s.lift > 0.002 || Math.abs(s.p) > 0.002;
    if (!active) {
      card.style.transform = c.base; card.style.setProperty("--lift", 0); card.style.setProperty("--rx", 0); card.style.setProperty("--ry", 0);
      card.style.zIndex = c.z0 || ""; c.anc.forEach(([a, z]) => (a.style.zIndex = z)); if (c.dim) c.dim.style.opacity = 0;
      return;
    }
    // 量出卡片「平放原位」在屏幕上的位置和大小
    card.style.transform = c.base;
    const r = card.getBoundingClientRect(), ps = r.width / (card.offsetWidth || 1) || 1;
    const vw = window.innerWidth, vh = window.innerHeight;
    const k = o.fill * Math.min(vw / r.width, vh / r.height);
    const dx = (vw / 2 + o.ox - (r.left + r.width / 2)) / ps, dy = (vh / 2 + o.oy - (r.top + r.height / 2)) / ps;
    // 「静而不死」:立起后持续缓慢漂移
    const L = clamp(s.lift), dr = o.drift * L;
    const rx = s.rx + dr * Math.sin(t * 0.83 + 0.6), ry = s.ry + dr * 1.35 * Math.sin(t * 0.57 + 1.9);
    const fy = dr * 3 * Math.sin(t * 0.71) / ps;
    const sc = lerp(1, k, s.p) * (1 - s.sq);
    if (c.persp == null) { const pp = card.parentElement && getComputedStyle(card.parentElement).perspective; c.persp = pp && pp !== "none" ? 0 : 1; }
    const pf = c.persp ? `perspective(${o.persp / ps / Math.max(sc, 0.01)}px) ` : "";
    // 注意 perspective 在 scale 之前 → 用 persp/sc 抵消缩放对透视强度的影响
    card.style.transform = `${c.base} translate3d(${dx * s.p}px,${dy * s.p + fy}px,0) scale(${sc}) ${pf}rotateX(${rx}deg) rotateY(${ry}deg) rotateZ(${s.rz}deg)`;
    card.style.setProperty("--lift", L.toFixed(4)); card.style.setProperty("--rx", rx.toFixed(3)); card.style.setProperty("--ry", ry.toFixed(3));
    // 层级:卡片及其祖先抬到最上,前面垫一层压暗
    if (getComputedStyle(card).position === "static") card.style.position = "relative";
    card.style.zIndex = 1000;
    if (!c.anc.length) { let a = card.parentElement; while (a && a !== document.body) { c.anc.push([a, a.style.zIndex]); a = a.parentElement; } }
    c.anc.forEach(([a]) => (a.style.zIndex = 1000));
    if (o.dim > 0) {
      if (!c.dim) { c.dim = mk("div", "hz-dim"); card.parentElement.insertBefore(c.dim, card); c.dim.style.zIndex = 999; }
      c.dim.style.opacity = (o.dim * L).toFixed(4);
      const b = o.dimBlur * L / ps;
      c.dim.style.backdropFilter = c.dim.style.webkitBackdropFilter = b > 0.05 ? `blur(${b}px)` : "none";
    }
  }
  // hz.dive(card, t0, {fill, rx, ry, rz, ox, oy, dim, dimBlur, drift, persp, peel, spring:[resp,damp], tilt:[resp,damp], cam})
  hz.dive = (card, t0, o = {}) => {
    card = hz.$(card); const c = ctl(card); o = Object.assign({}, DIVE, o);
    c.segs.push({ type: "dive", t0, o }); c.segs.sort((a, b) => a.t0 - b.t0); c.segs.forEach((g) => delete g.S);
    card.dataset.t0 = (t0 + o.lead + o.spring[0] * 1.1).toFixed(2);
    if (o.cam && typeof hz.camTo === "function") { try { hz.camTo(card, t0 - (o.camLead ?? 0.5), o.camOpts || {}); } catch (e) { console.warn("hz.camTo 调用失败", e); } }
    return card;
  };
  // hz.settle(card, t0, {spring, tilt, peel, cam})
  hz.settle = (card, t0, o = {}) => {
    card = hz.$(card); const c = ctl(card); o = Object.assign({}, DIVE, SETTLE, { lead: 0 }, o);
    c.segs.push({ type: "settle", t0, o }); c.segs.sort((a, b) => a.t0 - b.t0); c.segs.forEach((g) => delete g.S);
    if (o.cam && typeof hz.camTo === "function") { try { hz.camTo(card, t0, o.camOpts || {}); } catch (e) { console.warn("hz.camTo 调用失败", e); } }
    return card;
  };

  // ======================= UI 小部件 hz.w.* =======================
  const w = (hz.w = {});
  function caretOp(t, tEnd) {   // 输入中常亮,停下后柔和闪烁
    if (t < tEnd + 0.4) return 1;
    const v = Math.cos((t - tEnd - 0.4) * Math.PI * 2 * 0.9);
    return clamp(0.5 + v * 1.4);
  }

  // 输入框:hz.w.input(parent, {label, placeholder, text, at(开始输入), cps, focus(聚焦时刻,默认 at-0.35), blur(失焦时刻), appear, w, x, y})
  w.input = (parent, o = {}) => {
    const root = mk("div", "hz-w-field", parent); place(root, o);
    if (o.label) mk("div", "lb hz-txt", root, esc(o.label));
    const box = mk("div", "box", root);
    if (o.prefix) mk("span", "hz-txt", box, o.prefix).style.cssText = "font:500 25px Inter;color:var(--c-mute)";
    const ph = mk("div", "ph hz-txt", box, esc(o.placeholder || "")); if (o.prefix) ph.style.left = "auto";
    const v = mk("div", "v hz-txt", box);
    const chars = [...(o.text || "")].map((ch) => mk("span", "ch", v, esc(ch)));
    const cr = mk("span", "cr", v);
    const at = o.at ?? 1, cps = o.cps ?? 12, focus = o.focus ?? at - 0.35, blurT = o.blur ?? 1e9;
    const gaps = o.jitter === false ? null : chars.map((_, i) => 1 + 0.35 * Math.sin(i * 2.7 + 1.3));   // 打字节奏轻微不均匀,更像人
    const tc = []; let acc = at; chars.forEach((_, i) => { tc.push(acc); acc += (gaps ? gaps[i] : 1) / cps; });
    const tEnd = chars.length ? tc[tc.length - 1] : at;
    const fs = hz.spring(0.45, 0.75);
    hz.every((t) => {
      const f = t < blurT ? spr(t, focus, fs) : 1 - seg(t, blurT, 0.4);
      box.style.setProperty("--f", Math.max(0, f).toFixed(3));
      let n = 0;
      chars.forEach((c, i) => { const u = seg(t, tc[i], 0.14); if (t >= tc[i]) n++; c.style.opacity = u; c.style.transform = `translateY(${(1 - u) * 5}px)`; });
      ph.style.opacity = n ? 0 : 1 - 0.35 * clamp(f);
      cr.style.opacity = t >= focus && t < blurT ? caretOp(t, n < chars.length ? 1e9 : tEnd) * clamp(f * 2) : 0;
      cr.style.display = t >= focus && t < blurT ? "" : "none";
    });
    appear(root, o.appear);
    root.tDone = tEnd; return root;
  };

  // 按钮:hz.w.button(parent, {label, icon, press(时刻 或 [时刻...]), ripple(默认 true), rx, ry(波纹起点 0-1), pill, appear, w, x, y})
  w.button = (parent, o = {}) => {
    const root = mk("div", "hz-w-btn", parent); place(root, o);
    const face = mk("div", "face", root); if (o.pill) face.style.borderRadius = "999px"; if (o.h) face.style.height = o.h + "px";
    const rp = mk("span", "rp", face);
    const lbl = mk("span", "lbl hz-txt", face, (o.icon || "") + esc(o.label || "Button"));
    const presses = [].concat(o.press ?? []).sort((a, b) => a - b);
    const down = 0.09, rs = hz.spring(o.resp ?? 0.42, o.damp ?? 0.5);
    hz.every((t) => {
      let p = 0, rip = null;
      for (const tp of presses) {
        if (t < tp) break;
        const dt = t - tp;
        p = dt < down ? E.out(dt / down) : 1 - rs.f(dt - down);   // 按下 → 弹簧回弹(会越过 0 一点点 = 回弹)
        rip = dt;
      }
      face.style.transform = `translateY(${p * 2.5}px) scale(${1 - 0.055 * p})`;
      face.style.filter = p > 0.01 ? `brightness(${1 - 0.1 * p})` : "";
      face.style.setProperty("--p", clamp(p).toFixed(3));
      lbl.style.transform = `scale(${1 - 0.02 * p})`;
      if (o.ripple !== false && rip != null && rip < 0.9) {
        const u = E.out(clamp(rip / 0.75));
        rp.style.left = (o.rx ?? 0.5) * 100 + "%"; rp.style.top = (o.ry ?? 0.5) * 100 + "%";
        rp.style.transform = `scale(${0.3 + u * (face.offsetWidth / 40) * 2.2})`; rp.style.opacity = (1 - clamp(rip / 0.85)) * 0.4;
      } else rp.style.opacity = 0;
    });
    appear(root, o.appear);
    return root;
  };

  // 加载转圈:hz.w.spinner(parent, {t0(出现), t1(结束), done(结束时变形成勾,默认 true), size, text, doneText, appear, x, y})
  w.spinner = (parent, o = {}) => {
    const root = mk("div", "hz-w-spin", parent); place(root, o);
    const S = o.size || 44, R = S / 2 - 3, C = 2 * Math.PI * R;
    const wrap = mk("span", "", root); wrap.style.cssText = `position:relative;width:${S}px;height:${S}px;display:inline-block;flex:none`;
    wrap.innerHTML = `<svg width="${S}" height="${S}" viewBox="0 0 ${S} ${S}" style="position:absolute;inset:0;overflow:visible">
      <circle cx="${S / 2}" cy="${S / 2}" r="${R}" fill="none" stroke="var(--hz-line)" stroke-width="4"/>
      <circle class="a" cx="${S / 2}" cy="${S / 2}" r="${R}" fill="none" stroke="var(--c-main)" stroke-width="4" stroke-linecap="round"/>
      <circle class="b" cx="${S / 2}" cy="${S / 2}" r="${R}" fill="var(--c-accent)" opacity="0"/>
      <path class="k" d="M${S * 0.3} ${S * 0.52} L${S * 0.44} ${S * 0.66} L${S * 0.71} ${S * 0.37}" fill="none" stroke="var(--c-bg)" stroke-width="3.6" stroke-linecap="round" stroke-linejoin="round" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"/></svg>`;
    const a = wrap.querySelector(".a"), b = wrap.querySelector(".b"), k = wrap.querySelector(".k"), svg = wrap.querySelector("svg");
    const tx = o.text ? mk("span", "tx hz-txt", root, esc(o.text)) : null;
    const t0 = o.t0 ?? 0, t1 = o.t1 ?? 1e9, done = o.done !== false;
    const pop = hz.spring(0.5, 0.55);
    hz.every((t) => {
      const show = seg(t, t0, 0.35);
      const lt = t - t0;
      // 旋转 + 弧长呼吸
      const ang = lt * 300 + 70 * Math.sin(lt * 2.6);
      let len = 0.18 + 0.52 * (0.5 - 0.5 * Math.cos(lt * 2.6));
      let fillU = 0, kU = 0, sc = 0.6 + 0.4 * show;
      if (done && t >= t1) {
        const u = seg(t, t1, 0.32, E.inout); len = lerp(len, 1, u);
        fillU = seg(t, t1 + 0.22, 0.25); kU = seg(t, t1 + 0.32, 0.35);
        if (t > t1 + 0.22) sc *= 0.86 + 0.14 * pop.f(t - t1 - 0.22);   // 变形成勾时轻轻弹一下
      }
      a.setAttribute("stroke-dasharray", `${len * C} ${C}`);
      a.style.transform = `rotate(${ang}deg)`; a.style.transformOrigin = "50% 50%";
      b.setAttribute("opacity", fillU); k.style.strokeDashoffset = 1 - kU;
      svg.style.transform = `scale(${sc})`;
      root.style.opacity = !done && t >= t1 ? 1 - seg(t, t1, 0.3) : show;
      if (tx && o.doneText && t >= t1 + 0.2) tx.textContent = o.doneText; else if (tx) tx.textContent = o.text;
    });
    return root;
  };

  // 结果行:hz.w.results(parent, [{k, v, ok(默认 true), warn}], {t0, gap, icon(默认 true), appear, w, x, y})
  w.results = (parent, rows, o = {}) => {
    const root = mk("div", "hz-w-rows", parent); place(root, o);
    const t0 = o.t0 ?? 0, gap = o.gap ?? 0.16, pop = hz.spring(0.45, 0.55);
    rows.forEach((r, i) => {
      const row = mk("div", "hz-w-row", root);
      const ok = r.ok !== false;
      const col = r.warn || !ok ? "var(--c-warn)" : "var(--c-accent)";
      const ic = o.icon === false ? null : icoCheck(row, 28, `color-mix(in srgb, ${col} 20%, transparent)`, col);
      if (ic && !ok) ic.path.setAttribute("d", "M7 7 L17 17 M17 7 L7 17");
      mk("span", "k hz-txt", row, esc(r.k));
      const v = mk("span", "v hz-txt", row, esc(r.v));
      if (r.color) v.style.color = `var(--c-${r.color})`;
      const ti = t0 + i * gap;
      hz.every((t) => {
        const u = seg(t, ti, 0.5);
        row.style.opacity = u; row.style.transform = `translateY(${(1 - u) * 16}px)`; row.style.filter = u < 1 ? `blur(${(1 - u) * 5}px)` : "";
        if (ic) { ic.el.style.transform = `scale(${t < ti + 0.1 ? 0 : pop.f(t - ti - 0.1)})`; ic.path.style.strokeDashoffset = 1 - seg(t, ti + 0.18, 0.3); }
        v.style.transform = `translateX(${(1 - seg(t, ti + 0.05, 0.55)) * 10}px)`;
      });
    });
    return root;
  };

  // 列表/网格逐项点亮:hz.w.list(parent, [{label, miss, tag}], {cols, t0(出现), at(开始点亮), gap, missText, appear, w, x, y})
  w.list = (parent, items, o = {}) => {
    const root = mk("div", "hz-w-list", parent); place(root, o);
    root.style.gridTemplateColumns = `repeat(${o.cols || 1}, minmax(0, 1fr))`;
    const t0 = o.t0 ?? 0, at = o.at ?? t0 + 0.6, gap = o.gap ?? 0.18, pop = hz.spring(0.42, 0.55);
    items.forEach((it, i) => {
      if (typeof it === "string") it = { label: it };
      const el = mk("div", "hz-w-item", root);
      const ic = icoCheck(el, 26, "transparent", it.miss ? "var(--c-mute)" : "var(--hz-on-main)");
      ic.el.style.boxShadow = "inset 0 0 0 2px var(--hz-line)";
      if (it.miss) ic.path.setAttribute("d", "M7 12 L17 12");
      const lb = mk("span", "lb hz-txt", el, esc(it.label));
      const tag = mk("span", "tag hz-txt", el, esc(it.miss ? it.tag ?? o.missText ?? "未找到" : it.tag ?? ""));
      const ta = t0 + i * 0.05, tl = at + i * gap;
      hz.every((t) => {
        const u = seg(t, ta, 0.45);
        el.style.opacity = it.miss ? u * (1 - 0.55 * seg(t, tl, 0.4)) : u;
        el.style.transform = `translateY(${(1 - u) * 12}px)`;
        if (!it.miss) {
          const on = seg(t, tl, 0.35);
          el.style.setProperty("--on", on.toFixed(3));
          ic.el.style.background = on > 0 ? `color-mix(in srgb, var(--c-main) ${on * 100}%, transparent)` : "transparent";
          ic.el.style.boxShadow = `inset 0 0 0 ${2 * (1 - on)}px var(--hz-line)`;
          ic.el.style.transform = `scale(${t < tl ? 1 : 0.7 + 0.3 * pop.f(t - tl)})`;
          ic.path.style.strokeDashoffset = 1 - seg(t, tl + 0.08, 0.3);
          tag.style.opacity = on;
        } else {
          ic.path.style.strokeDashoffset = 1 - seg(t, tl, 0.25);
          lb.style.textDecoration = t >= tl ? "line-through" : "none"; lb.style.color = t >= tl ? "var(--c-mute)" : "";
          tag.style.opacity = seg(t, tl, 0.35);
        }
      });
    });
    appear(root, o.appear);
    return root;
  };

  // 终端:hz.w.terminal(parent, [{cmd, at, out:[行 或 {s, ok, err}], wait, gap}], {title, t0, cps, rows(可见行数), prompt, w, x, y, appear})
  w.terminal = (parent, cmds, o = {}) => {
    const root = mk("div", "hz-w-term", parent); place(root, o);
    const hd = mk("div", "hd", root);
    ["var(--c-warn)", "color-mix(in srgb, var(--c-warn) 50%, var(--c-accent))", "var(--c-accent)"].forEach((c) => (mk("i", "", hd).style.background = c));
    mk("span", "tt hz-txt", hd, esc(o.title || "zsh"));
    const bd = mk("div", "bd", root), sc = mk("div", "sc", bd);
    const LH = 19 * 1.65, rowsVis = o.rows || 8; bd.style.height = rowsVis * LH + 32 + "px";
    const cps = o.cps ?? 22, prompt = o.prompt ?? "$";
    let tt = o.t0 ?? 0; const lines = [];   // {el, t}
    cmds.forEach((c) => {
      const at = c.at ?? tt;
      const ln = mk("div", "ln hz-txt", sc); ln.innerHTML = `<span class="pr">${esc(prompt)}</span> <span class="cm"></span>`;
      const cm = ln.querySelector(".cm"), cr = mk("span", "cr", ln);
      const cc = c.cps ?? cps, txt = [...c.cmd], tEnd = at + txt.length / cc, tEnter = tEnd + (c.enter ?? 0.3);
      lines.push({ el: ln, t: at - 0.01 });
      hz.every((t) => {
        const n = clamp(Math.floor((t - at) * cc), 0, txt.length);
        cm.textContent = txt.slice(0, n).join("");
        cr.style.display = t >= at - 0.3 && t < tEnter ? "" : "none";
        cr.style.opacity = caretOp(t, n < txt.length ? 1e9 : tEnd);
        cr.style.background = "var(--c-ink)";
      });
      let to = tEnter + (c.wait ?? 0.25);
      (c.out || []).forEach((s) => {
        if (typeof s === "string") s = { s };
        const ol = mk("div", "ln hz-txt" + (s.ok ? " ok" : "") + (s.err ? " er" : ""), sc, esc(s.s));
        lines.push({ el: ol, t: to }); to += s.d ?? c.gap ?? 0.09;
      });
      tt = to + (c.next ?? 0.45);
    });
    hz.every((t) => {
      let shown = 0;
      lines.forEach((l) => { const u = seg(t, l.t, 0.18); l.el.style.display = t >= l.t ? "" : "none"; l.el.style.opacity = u; shown += u; });
      const ov = Math.max(0, shown - rowsVis); sc.style.transform = `translateY(${-(ov * LH + Math.min(1, ov) * 10)}px)`;
    });
    appear(root, o.appear);
    root.tDone = tt; return root;
  };

  // 进度条:hz.w.progress(parent, {label, t0, t1, from=0, to=100, keys:[{t, v}](可代替 t0/t1), pct(显示百分比,默认 true), appear, w, x, y})
  w.progress = (parent, o = {}) => {
    const root = mk("div", "hz-w-prog", parent); place(root, o);
    const top = mk("div", "top", root);
    mk("span", "lb hz-txt", top, esc(o.label || ""));
    const pc = mk("span", "pc hz-txt", top);
    const tr = mk("div", "tr", root), fl = mk("div", "fl", tr), sh = mk("div", "sh", fl);
    const keys = o.keys || [{ t: o.t0 ?? 0, v: o.from ?? 0 }, { t: o.t1 ?? 1, v: o.to ?? 100 }];
    hz.every((t) => {
      const v = hz.val(keys.map((k) => ({ t: k.t, v: k.v, e: k.e || E.inout })), "v", t);
      fl.style.width = clamp(v / 100) * 100 + "%";
      pc.textContent = o.pct === false ? "" : Math.round(v) + "%";
      sh.style.left = `${((t * 0.9) % 1.4) * 100 - 20}%`; sh.style.opacity = v < 100 ? 1 : 0;
    });
    if (o.pct === false) pc.style.display = "none";
    appear(root, o.appear);
    return root;
  };

  // 鼠标光标:hz.w.cursor(parent, [{t(到达时刻), x, y | el(+dx,dy 偏移,默认元素中心), d(移动用时,默认 0.7), click}], {t0(出现), t1(消失), size})
  // 坐标是 parent 内的 px(不受 3D 变换影响,跟着卡片一起倾斜)。click: true 表示到达后 0.06s 点击,也可以给具体时刻
  w.cursor = (parent, keys, o = {}) => {
    parent = hz.$(parent);
    const root = mk("div", "hz-w-cursor", parent);
    const S = o.size || 34;
    root.innerHTML = `<div class="ring"></div><svg width="${S}" height="${S}" viewBox="0 0 44 44"><path d="M8 4 L8 36 L16 28 L22 41 L28 38 L22 26 L33 26 Z" fill="var(--c-ink)" stroke="var(--c-bg)" stroke-width="2.6" stroke-linejoin="round"/></svg>`;
    const ring = root.querySelector(".ring"), svg = root.querySelector("svg");
    const pos = (k) => {
      if (!k.el) return [k.x || 0, k.y || 0];
      let e = hz.$(k.el), x = 0, y = 0; const W = e.offsetWidth, H = e.offsetHeight;
      while (e && e !== parent) { x += e.offsetLeft; y += e.offsetTop; e = e.offsetParent; }
      return [x + (k.dx ?? W / 2), y + (k.dy ?? H / 2)];
    };
    keys = keys.slice().sort((a, b) => a.t - b.t);
    const clicks = keys.filter((k) => k.click).map((k) => (k.click === true ? k.t + 0.06 : k.click));
    const t0 = o.t0 ?? keys[0].t - 0.4, t1 = o.t1 ?? 1e9, cs = hz.spring(0.32, 0.5);
    const at = (t) => {
      let P = pos(keys[0]);
      for (let i = 1; i < keys.length; i++) {
        const k = keys[i], d = k.d ?? 0.7;
        if (t <= k.t - d) break;
        const Q = pos(k), u = MOVE(clamp((t - (k.t - d)) / d));
        // 轻微弧线:中段向上拱一点
        const arc = bump(u) * Math.min(40, Math.hypot(Q[0] - P[0], Q[1] - P[1]) * 0.08);
        P = [lerp(P[0], Q[0], u), lerp(P[1], Q[1], u) - arc];
      }
      return P;
    };
    hz.every((t) => {
      const [x, y] = at(t), [x2] = at(t - 1 / 30);
      const vx = (x - x2) * 30;
      let s = 1, rg = null;
      for (const c of clicks) if (t >= c) { const dt = t - c; s = dt < 0.07 ? 1 - 0.18 * E.out(dt / 0.07) : 0.82 + 0.18 * cs.f(dt - 0.07); rg = dt; }
      root.style.transform = `translate(${x}px,${y}px)`;
      svg.style.transform = `rotate(${clamp(vx / 220, -1, 1) * -7}deg) scale(${s})`; svg.style.transformOrigin = "5px 3px";
      root.style.opacity = seg(t, t0, 0.3) * (1 - seg(t, t1, 0.3));
      if (rg != null && rg < 0.6) { const u = E.out(clamp(rg / 0.5)); ring.style.opacity = (1 - u) * 0.9; ring.style.transform = `scale(${0.3 + u * 1.1})`; } else ring.style.opacity = 0;
    });
    return root;
  };
})();
