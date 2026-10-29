/* hz_kit.js —— 动画库存 hz.k.*:案例段用的「真实截图 + UI 假窗 + 交互动画」。
   在 hz.js、hz_ui3d.js、hz_3d.js、hz_type.js 之后加载。参数表和用法见 规范/02_合成师_动画与素材库.md。
   - 截图窗 shot(按百分比裁切 + 按名字取框选区域)、框选 frame、高亮脉冲 pulse、浏览器假窗 browser(spinner → 内容)、
     改版前后 swap、pills 逐项点亮 pills、代码块 code(逐字 + 行高亮)、面板滑入 panel、满幅暗场 dark。
   - 终端 / 转圈 / 光标 / 列表 / 结果行 / 进度条仍用 hz.w.*,数字跳动仍用 hz.t.count;加载本文件后它们也会被记账。
   - 每个交互动画都记进 hz.k.log([{kind, t, d}]),hz check 用它核对「案例段有没有交互」;UI 根元素带 class hz-ui,检查器用它量画面占比。
   版本规则:函数只增不改。要改已有函数的行为就起新名字(如 frame2),旧集重渲不受影响;改动记在 规范/02 的「版本记录」。
   所有动画按绝对时间 t 计算(纯函数),交给 hz.every 每帧调用。颜色只用 CSS 变量。 */
(function () {
  const hz = window.hz; if (!hz || !hz.w || !hz.t) throw new Error("hz_kit.js 要在 hz.js、hz_ui3d.js、hz_type.js 之后加载");
  const E = hz.ease, cl = hz.clamp, lerp = hz.lerp;
  const stop = () => E.stop || E.out;
  const seg = (t, a, d) => cl((t - a) / d);
  const bump = (u) => (u <= 0 || u >= 1 ? 0 : Math.sin(Math.PI * u));
  const mk = (tag, cls, par, css, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (css) e.style.cssText = css; if (html != null) e.innerHTML = html; if (par) hz.$(par).appendChild(e); return e; };
  const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;");
  const place = (el, o) => { if (o.x != null || o.y != null) { el.style.position = "absolute"; el.style.left = (o.x || 0) + "px"; el.style.top = (o.y || 0) + "px"; } };
  const mark = (el, t) => { el.classList.add("hz-txt"); el.dataset.t0 = (+t).toFixed(3); return el; };
  const ui = (el) => { el.classList.add("hz-ui"); return el; };
  const rectOf = (r) => (Array.isArray(r) ? { x: r[0], y: r[1], w: r[2], h: r[3] } : r);

  const K = (hz.k = { v: "1.1", log: [] });
  // 计入「交互」的动画种类(hz check 只数这些;panel / dark 是出场和底色,不算交互)
  K.KINDS = ["frame", "pulse", "count", "terminal", "load", "swap", "pills", "click", "code", "hl", "list", "results", "progress", "input"];
  const note = (kind, t, d = 0) => { K.log.push({ kind, t: +(+t).toFixed(3), d: +(+d).toFixed(3) }); };
  K.note = note;

  // 图片先解码再定格(不然第一帧可能是空白)
  const PEND = [];
  { const _seek = window.HZ.seek; window.HZ.seek = async (t) => { if (PEND.length) await Promise.all(PEND.splice(0).map((im) => (im.decode ? im.decode().catch(() => {}) : 0))); return _seek(t); }; }

  const CSS = `
:root{--k-frame:var(--c-accent);--k-frame-ink:var(--c-on-accent,#fff);--k-dark:var(--c-dark,var(--c-ink));--k-code:var(--c-dark,var(--c-ink))}
.hz-k-shot{position:relative;overflow:hidden;border-radius:14px;background:var(--c-card);box-shadow:0 34px 80px -34px color-mix(in srgb,var(--c-ink) 50%,transparent),0 0 0 1px color-mix(in srgb,var(--c-ink) 10%,transparent)}
.hz-k-shot>img{position:absolute;display:block;max-width:none;user-select:none}
.hz-k-frame{position:absolute;pointer-events:none}
.hz-k-frame svg{position:absolute;left:0;top:0;overflow:visible}
.hz-k-frame .gl{position:absolute;inset:0;border-radius:inherit;box-shadow:0 0 0 3px color-mix(in srgb,var(--k-frame) 30%,transparent),0 0 28px color-mix(in srgb,var(--k-frame) 60%,transparent);opacity:0}
.hz-k-frame .sw{position:absolute;inset:0;overflow:hidden;border-radius:inherit}
.hz-k-frame .sw i{position:absolute;top:-30%;bottom:-30%;width:42%;background:linear-gradient(90deg,transparent,color-mix(in srgb,var(--c-card) 60%,transparent),transparent);transform:skewX(-18deg)}
.hz-k-dim{position:absolute;pointer-events:none;box-shadow:0 0 0 4000px color-mix(in srgb,var(--k-dark) 46%,transparent);opacity:0}
.hz-k-tag{position:absolute;display:inline-flex;align-items:center;gap:8px;padding:9px 15px 10px;border-radius:10px;background:var(--k-frame);color:var(--k-frame-ink);font:700 24px/1 "Noto Sans SC",Inter;white-space:nowrap;box-shadow:0 12px 26px -12px color-mix(in srgb,var(--c-ink) 65%,transparent)}
.hz-k-tag.ink{background:var(--c-ink);color:var(--c-card)}
.hz-k-ring{position:absolute;pointer-events:none;border:3px solid var(--k-frame);opacity:0}
.hz-k-br{position:relative;border-radius:16px;overflow:hidden;background:var(--c-card);box-shadow:0 40px 90px -36px color-mix(in srgb,var(--c-ink) 55%,transparent),0 0 0 1px color-mix(in srgb,var(--c-ink) 10%,transparent)}
.hz-k-br .bar{position:relative;height:48px;display:flex;align-items:center;gap:9px;padding:0 18px;background:color-mix(in srgb,var(--c-card) 90%,var(--c-ink));border-bottom:1px solid var(--c-line)}
.hz-k-br .bar>i{width:13px;height:13px;border-radius:50%;background:color-mix(in srgb,var(--c-ink) 20%,var(--c-card))}
.hz-k-br .url{flex:1;margin-left:16px;height:30px;border-radius:9px;background:var(--c-card);box-shadow:inset 0 0 0 1px var(--c-line);display:flex;align-items:center;gap:9px;padding:0 14px;font:500 17px/1 "JetBrains Mono";color:var(--c-mute);overflow:hidden;white-space:nowrap}
.hz-k-br .url b{font-weight:500;color:var(--c-ink)}
.hz-k-br .pg{position:absolute;left:0;bottom:-1px;height:3px;width:0;background:var(--c-main)}
.hz-k-br .body{position:relative;overflow:hidden;background:var(--c-card)}
.hz-k-br .ct{position:relative}
.hz-k-br .sk{position:absolute;inset:0;padding:36px 42px;display:flex;flex-direction:column;gap:20px;opacity:0}
.hz-k-br .sk b{display:block;height:22px;border-radius:7px;background:color-mix(in srgb,var(--c-ink) 8%,transparent)}
.hz-k-br .sp{position:absolute;left:50%;top:50%;width:58px;height:58px;margin:-29px;opacity:0}
.hz-k-swap{position:relative}
.hz-k-swap>.pane{position:absolute;left:0;top:0}
.hz-k-swap>.fl{position:absolute;inset:-2px;border-radius:16px;background:var(--c-card);opacity:0;pointer-events:none}
.hz-k-swap>.dv{position:absolute;top:-10px;bottom:-10px;width:4px;margin-left:-2px;border-radius:2px;background:var(--k-frame);opacity:0}
.hz-k-pills{display:flex;flex-wrap:wrap;gap:16px 18px}
.hz-k-pill{display:inline-flex;align-items:center;gap:12px;padding:13px 24px 13px 14px;border-radius:999px;background:var(--c-card);box-shadow:inset 0 0 0 1.5px var(--c-line),0 14px 30px -18px color-mix(in srgb,var(--c-ink) 50%,transparent);font:600 28px/1 "Noto Sans SC",Inter;color:var(--c-ink);white-space:nowrap}
.hz-k-pill .ck{width:32px;height:32px;border-radius:50%;flex:none;display:inline-flex;align-items:center;justify-content:center;box-shadow:inset 0 0 0 2px var(--c-line)}
.hz-k-code{position:relative;border-radius:16px;overflow:hidden;background:var(--k-code);color:var(--c-card);box-shadow:0 40px 90px -36px color-mix(in srgb,var(--c-ink) 60%,transparent)}
.hz-k-code.light{background:var(--c-card);color:var(--c-ink);box-shadow:0 40px 90px -36px color-mix(in srgb,var(--c-ink) 50%,transparent),0 0 0 1px color-mix(in srgb,var(--c-ink) 10%,transparent)}
.hz-k-code .hd{height:44px;display:flex;align-items:center;gap:9px;padding:0 18px;border-bottom:1px solid color-mix(in srgb,currentColor 12%,transparent)}
.hz-k-code .hd i{width:12px;height:12px;border-radius:50%;background:color-mix(in srgb,currentColor 25%,transparent)}
.hz-k-code .hd span{margin-left:12px;font:500 16px/1 "JetBrains Mono";opacity:.6}
.hz-k-code .bd{position:relative;padding:22px 0 24px}
.hz-k-code .ln{position:relative;display:flex;font:500 var(--k-fs,24px)/1.75 "JetBrains Mono";white-space:pre;padding-right:32px}
.hz-k-code .no,.hz-k-code .cd{position:relative}
.hz-k-code .no{width:60px;text-align:right;padding-right:20px;opacity:.32;flex:none}
.hz-k-code .hl{position:absolute;left:0;right:0;top:0;bottom:0;background:color-mix(in srgb,var(--c-main) 26%,transparent);box-shadow:inset 4px 0 0 var(--c-main);transform-origin:0 50%;transform:scaleX(0)}
.hz-k-code .t-k{color:color-mix(in srgb,var(--c-main) 70%,var(--c-card))}.hz-k-code .t-s{color:var(--c-mark)}.hz-k-code .t-n{color:var(--c-accent)}.hz-k-code .t-c{opacity:.45}
.hz-k-code.light .t-k{color:var(--c-main)}.hz-k-code.light .t-s{color:var(--c-accent)}
.hz-k-code .cr{display:inline-block;width:.55em;height:1.1em;vertical-align:-.2em;background:currentColor}
.hz-k-dark{position:absolute;inset:0;opacity:0;pointer-events:none}
/* hz_canvas.js 给所有 .hz-txt 写死了墨色;深色底上的字要跟随父元素颜色(深色纸片、代码块) */
.hz-k-code .cd,.hz-chip.dark .tx{color:inherit}
.hz-k-code .cd{white-space:pre}   /* .hz-txt 是 nowrap,会吞掉代码缩进 */
:root .hz-w-term .ln.ok{color:var(--k-ok,var(--c-main))}   /* hz_ui3d 终端把「成功」行画成 accent(本风格是橙色,像报错) */
`;
  const st = document.createElement("style"); st.id = "hz-kit-css"; st.textContent = CSS; document.head.appendChild(st);

  const icoCheck = (par, size) => {
    const e = mk("span", "ck", par);
    e.innerHTML = `<svg width="${size * 0.56}" height="${size * 0.56}" viewBox="0 0 24 24"><path d="M5 12.5 L10 17 L19 7.5" fill="none" stroke="var(--c-card)" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"/></svg>`;
    return { el: e, path: e.querySelector("path") };
  };

  // ======================= 截图窗 =======================
  // hz.k.shot(par, {src, size:[原图宽,原图高], w 显示宽, crop:[x,y,w,h](0–1,默认整张), boxes:{名字:[x,y,w,h](0–1,相对整张原图)}, x, y, r 圆角})
  // size / boxes 照抄截图同名 .json(hz capture 生成)。返回根元素;root.box(名字 | [x,y,w,h], pad) → 该区域在根元素里的 {x,y,w,h}(px)
  K.shot = (par, o) => {
    if (!o.size) throw new Error(`hz.k.shot(${o.src}) 缺 size:[宽,高](截图同名 .json 里有)`);
    const [cx, cy, cw, ch] = o.crop || [0, 0, 1, 1], [nw, nh] = o.size;
    const w = o.w || 960, s = w / (cw * nw), h = Math.round(ch * nh * s);
    const root = ui(mk("div", "hz-k-shot", par, `width:${w}px;height:${h}px` + (o.r != null ? `;border-radius:${o.r}px` : "")));
    place(root, o);
    const img = mk("img", "", root, `left:${(-cx * nw * s).toFixed(2)}px;top:${(-cy * nh * s).toFixed(2)}px;width:${(nw * s).toFixed(2)}px;height:${(nh * s).toFixed(2)}px`);
    img.alt = ""; img.src = o.src; PEND.push(img);
    root.img = img; root.W = w; root.H = h; root.k = s;
    root.box = (b, pad = 0) => {
      if (typeof b === "string") { if (!o.boxes || !o.boxes[b]) throw new Error(`截图 ${o.src} 没有框选区域「${b}」(看同名 .json 的 boxes)`); b = o.boxes[b]; }
      return { x: (b[0] - cx) * nw * s - pad, y: (b[1] - cy) * nh * s - pad, w: b[2] * nw * s + 2 * pad, h: b[3] * nh * s + 2 * pad };
    };
    return root;
  };

  // 区域换算:rect 是元素 from 里的坐标 → 换成祖先元素 to 里的坐标(把框/标签放到不裁切的外层时用)
  K.rel = (rect, from, to) => { const R = rectOf(rect); let x = R.x, y = R.y; for (let e = from; e && e !== to; e = e.offsetParent) { x += e.offsetLeft; y += e.offsetTop; } return { x, y, w: R.w, h: R.h }; };

  // ======================= 框选 =======================
  // hz.k.frame(par, 区域 {x,y,w,h} | [x,y,w,h](px,通常用 shot.box("名字")), {t0 开始画, d=0.45 画框用时, t1 淡出时刻, pad=8, r=10, w=3,
  //   label 呼出标签文字, labelAt:"auto"|"top"|"bottom"|"right"|"left"|"in", sweep=true 扫光一次, breathe=true 呼吸, dim=0 框外压暗(0–1,只在会裁切的父元素里用,如 shot/browser)})
  // 标签放在框外;父元素会裁切(shot)时 auto 只在上/下/框内里选,要放到截图外面就把 par 换成截图所在的图层 .in(区域坐标不变)
  K.frame = (par, rect, o = {}) => {
    const R = rectOf(rect), pad = o.pad ?? 8, t0 = o.t0 ?? 0, d = o.d ?? 0.45, t1 = o.t1 ?? 1e9, sw = o.w ?? 3, rr = o.r ?? 10;
    const x = R.x - pad, y = R.y - pad, w = R.w + 2 * pad, h = R.h + 2 * pad;
    const dim = o.dim ? mk("div", "hz-k-dim", par, `left:${x}px;top:${y}px;width:${w}px;height:${h}px;border-radius:${rr}px`) : null;
    const el = mk("div", "hz-k-frame", par, `left:${x}px;top:${y}px;width:${w}px;height:${h}px;border-radius:${rr}px`);
    const gl = mk("div", "gl", el), swp = o.sweep === false ? null : mk("div", "sw", el, "", "<i></i>").firstChild;
    el.insertAdjacentHTML("beforeend", `<svg width="${w}" height="${h}"><rect x="${sw / 2}" y="${sw / 2}" width="${w - sw}" height="${h - sw}" rx="${rr}" fill="none" stroke="var(--k-frame)" stroke-width="${sw}" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"/></svg>`);
    const line = el.querySelector("rect");
    let tag = null;
    if (o.label) {
      tag = mark(mk("div", "hz-k-tag", par, "", esc(o.label)), t0 + d * 0.7 + 0.25);
      const PH = par.H || par.offsetHeight || 1e9, TH = 46;
      const at = o.labelAt && o.labelAt !== "auto" ? o.labelAt : y >= TH + 10 ? "top" : y + h + TH + 10 <= PH ? "bottom" : "in";
      tag.style.left = (at === "right" ? x + w + 12 : at === "in" ? x + 8 : x) + "px";
      tag.style.top = (at === "top" ? y - TH - 8 : at === "bottom" ? y + h + 8 : at === "in" ? y + 8 : y + h / 2 - TH / 2) + "px";
      if (at === "left") { tag.style.left = "auto"; tag.style.right = `calc(100% - ${x - 12}px)`; }
    }
    const tEnd = t0 + d;
    hz.every((t) => {
      const on = t >= t0 - 0.02, out = E.inout(seg(t, t1, 0.3)), v = stop()(seg(t, t0, d));
      el.style.visibility = on && out < 1 ? "" : "hidden";
      line.style.strokeDashoffset = (1 - v).toFixed(4);
      el.style.opacity = (1 - out).toFixed(3);
      el.style.scale = lerp(1.06, 1, v).toFixed(4);
      const br = o.breathe === false ? 1 : 0.62 + 0.38 * Math.cos((2 * Math.PI * Math.max(0, t - tEnd)) / 1.5);
      gl.style.opacity = (seg(t, tEnd - 0.1, 0.25) * br * (1 - out)).toFixed(3);
      if (swp) { const u = seg(t, tEnd - 0.05, 0.6); swp.style.left = `${lerp(-50, 110, E.inout(u)).toFixed(2)}%`; swp.style.opacity = u > 0 && u < 1 ? 1 : 0; }
      if (dim) dim.style.opacity = (o.dim * E.inout(seg(t, t0, d)) * (1 - out)).toFixed(3);
      if (tag) { const u = seg(t, t0 + d * 0.7, 0.25), q = stop()(u);
        tag.style.visibility = u > 0 && out < 1 ? "" : "hidden"; tag.style.opacity = (cl(u * 2.5) * (1 - out)).toFixed(3);
        tag.style.translate = `0 ${(10 * (1 - q)).toFixed(1)}px`; tag.style.scale = lerp(0.9, 1, q).toFixed(4); }
    });
    note("frame", t0, d); el.tag = tag; return el;
  };

  // ======================= 高亮脉冲 =======================
  // hz.k.pulse(par, 区域, {t0, n=2 圈数, gap=0.32, d=0.7 每圈时长, r=12, grow=0.35 放大比例, fill=true 区域内闪一下})
  K.pulse = (par, rect, o = {}) => {
    const R = rectOf(rect), t0 = o.t0 ?? 0, n = o.n ?? 2, gap = o.gap ?? 0.32, d = o.d ?? 0.7, rr = o.r ?? 12, grow = o.grow ?? 0.35;
    const box = `left:${R.x}px;top:${R.y}px;width:${R.w}px;height:${R.h}px;border-radius:${rr}px`;
    const fill = o.fill === false ? null : mk("div", "hz-k-ring", par, box + ";border:none;background:color-mix(in srgb,var(--k-frame) 22%,transparent)");
    const rings = Array.from({ length: n }, () => mk("div", "hz-k-ring", par, box));
    hz.every((t) => {
      rings.forEach((g, i) => { const u = seg(t, t0 + i * gap, d), q = E.out(u);
        g.style.opacity = u > 0 && u < 1 ? ((1 - q) * 0.95).toFixed(3) : 0; g.style.scale = lerp(1, 1 + grow, q).toFixed(4); });
      if (fill) fill.style.opacity = (bump(seg(t, t0, 0.5)) * 0.9).toFixed(3);
    });
    note("pulse", t0, (n - 1) * gap + d);
    return rings;
  };

  // ======================= 浏览器假窗 =======================
  // hz.k.browser(par, {w=1000, h 窗口总高(省略 = 跟内容走), url, typeAt 地址栏打字开始(省略 = 一直显示), cps=26,
  //   load:[t0,t1] 加载中(顶部进度条 + 骨架屏 + 转圈)→ t1 出内容, src/size/crop/boxes 直接放一张截图当内容, content 自己的内容元素, x, y})
  // 返回根元素;root.body 内容区,root.shot 截图窗(给了 src 才有,可直接 root.shot.box("名字") 框选)
  K.browser = (par, o = {}) => {
    const w = o.w || 1000, BH = 48;
    const root = ui(mk("div", "hz-k-br", par, `width:${w}px`)); place(root, o);
    const bar = mk("div", "bar", root, "", "<i></i><i></i><i></i>");
    const url = mk("div", "url", bar, "", `<svg width="14" height="16" viewBox="0 0 14 16"><rect x="1.5" y="7" width="11" height="8" rx="2" fill="currentColor"/><path d="M4 7V5a3 3 0 0 1 6 0v2" fill="none" stroke="currentColor" stroke-width="1.8"/></svg><b></b>`);
    const ut = url.querySelector("b"), pg = mk("div", "pg", bar);
    const body = mk("div", "body", root), ct = mk("div", "ct", body);
    root.body = ct;
    if (o.src) root.shot = K.shot(ct, { src: o.src, size: o.size, crop: o.crop, boxes: o.boxes, w, r: 0 });
    if (o.content) ct.appendChild(o.content);
    if (o.h) body.style.height = o.h - BH + "px";
    const U = [...(o.url || "")], cps = o.cps ?? 26;
    const [l0, l1] = o.load || [null, null];
    const sk = l0 == null ? null : mk("div", "sk", body, "", "<b style='width:46%'></b><b style='width:88%;height:120px'></b><b style='width:72%'></b><b style='width:80%'></b>");
    const sp = l0 == null ? null : mk("div", "sp", body, "", `<svg width="58" height="58" viewBox="0 0 58 58"><circle cx="29" cy="29" r="24" fill="none" stroke="var(--c-line)" stroke-width="5"/><circle cx="29" cy="29" r="24" fill="none" stroke="var(--c-main)" stroke-width="5" stroke-linecap="round" stroke-dasharray="40 200"/></svg>`);
    hz.every((t) => {
      const n = o.typeAt == null ? U.length : cl(Math.floor((t - o.typeAt) * cps), 0, U.length);
      ut.textContent = U.slice(0, n).join("");
      if (l0 == null) return;
      const lu = seg(t, l0, l1 - l0), cu = seg(t, l1, 0.4), cq = stop()(cu);
      pg.style.width = (t < l0 ? 0 : t < l1 ? 88 * E.out(lu) : 100) + "%";
      pg.style.opacity = t < l1 ? 1 : 1 - seg(t, l1 + 0.1, 0.25);
      ct.style.opacity = cq.toFixed(3); ct.style.translate = `0 ${(14 * (1 - cq)).toFixed(1)}px`; ct.style.filter = cu > 0 && cu < 1 ? `blur(${(6 * (1 - cq)).toFixed(2)}px)` : "";
      ct.style.visibility = cu > 0 ? "" : "hidden";
      sk.style.opacity = (t >= l0 - 0.05 ? 1 - cu : 0).toFixed(3);
      sk.querySelectorAll("b").forEach((b, i) => (b.style.opacity = (0.55 + 0.45 * Math.cos(t * 5 - i * 0.7)).toFixed(3)));
      sp.style.opacity = (seg(t, l0, 0.15) * (1 - seg(t, l1 - 0.1, 0.2))).toFixed(3);
      sp.style.rotate = `${(t * 400) % 360}deg`;
    });
    if (l0 != null) note("load", l1, l1 - l0);
    return root;
  };

  // ======================= 改版前后 =======================
  // hz.k.swap(par, {before 元素, after 元素, at 切换时刻, back 切回时刻(可省), t0 本块出现时刻(给「改版前」标签算展示时长,默认 at-1),
  //   w, h 尺寸(默认量 before), labels:["改版前","改版后"](false = 不要标签), mode:"flash"|"wipe", x, y})
  K.swap = (par, o) => {
    const root = ui(mk("div", "hz-k-swap", par)); place(root, o);
    const A = mk("div", "pane", root), B = mk("div", "pane", root);
    A.appendChild(o.before); B.appendChild(o.after);
    const w = o.w || o.before.offsetWidth, h = o.h || o.before.offsetHeight;
    root.style.width = w + "px"; root.style.height = h + "px";
    const fl = mk("div", "fl", root), dv = o.mode === "wipe" ? mk("div", "dv", root) : null;
    const at = o.at, back = o.back ?? 1e9, t0 = o.t0 ?? at - 1, d = o.mode === "wipe" ? 0.55 : 0.12;
    const L = o.labels === false ? null : (o.labels || ["改版前", "改版后"]).map((s, i) => mark(mk("div", "hz-k-tag ink", root, "left:16px;top:16px", esc(s)), i ? at + d + 0.1 : t0));
    if (L) { L[1].style.background = "var(--k-frame)"; L[1].style.color = "var(--k-frame-ink)"; }
    hz.every((t) => {
      const u = (o.mode === "wipe" ? E.inout : E.out)(seg(t, at, d)) * (1 - E.out(seg(t, back, d)));
      if (o.mode === "wipe") { B.style.clipPath = `inset(0 ${((1 - u) * 100).toFixed(2)}% 0 0)`; dv.style.left = (u * 100).toFixed(2) + "%"; dv.style.opacity = u > 0.01 && u < 0.99 ? 1 : 0; }
      else { B.style.opacity = u.toFixed(3); A.style.opacity = (1 - u).toFixed(3); fl.style.opacity = (bump(seg(t, at - 0.04, 0.3)) * 0.85 + bump(seg(t, back - 0.04, 0.3)) * 0.85).toFixed(3); }
      root.style.scale = (1 + 0.025 * bump(seg(t, at, 0.35)) + 0.025 * bump(seg(t, back, 0.35))).toFixed(4);
      if (L) { const k = u > 0.5 ? 1 : 0; L.forEach((g, i) => { g.style.visibility = i === k ? "" : "hidden"; }); L[k].style.translate = `0 ${(-8 * bump(seg(t, k ? at : back, 0.25))).toFixed(1)}px`; }
    });
    note("swap", at, d); if (o.back != null) note("swap", back, d);
    root.A = A; root.B = B; return root;
  };

  // ======================= pills 逐项点亮 =======================
  // hz.k.pills(par, ["A", {label, miss}], {t0 出现, at 开始点亮, gap=0.16 每项间隔, size 字号(默认 28), w 换行宽度, x, y})
  K.pills = (par, items, o = {}) => {
    const root = ui(mk("div", "hz-k-pills", par)); place(root, o);
    if (o.w) root.style.width = o.w + "px";
    const t0 = o.t0 ?? 0, at = o.at ?? t0 + 0.5, gap = o.gap ?? 0.16, pop = hz.spring(0.4, 0.5);
    items.forEach((it, i) => {
      if (typeof it === "string") it = { label: it };
      const el = mk("div", "hz-k-pill", root); if (o.size) el.style.fontSize = o.size + "px";
      const ic = icoCheck(el, 32), lb = mark(mk("span", "", el, "", esc(it.label)), t0 + i * 0.05 + 0.35);
      if (it.miss) ic.path.setAttribute("d", "M7 12 L17 12");
      const ta = t0 + i * 0.05, tl = at + i * gap;
      hz.every((t) => {
        const u = seg(t, ta, 0.35), q = stop()(u), on = seg(t, tl, 0.3);
        el.style.visibility = u > 0 ? "" : "hidden"; el.style.opacity = (cl(u * 2) * (it.miss ? 1 - 0.5 * on : 1)).toFixed(3);
        el.style.translate = `0 ${(12 * (1 - q)).toFixed(1)}px`;
        el.style.scale = (t < tl ? 1 : 0.94 + 0.06 * pop.f(t - tl)).toFixed(4);
        if (it.miss) { lb.style.textDecoration = t >= tl ? "line-through" : "none"; ic.el.style.background = on > 0 ? "var(--c-mute)" : "transparent"; }
        else {
          el.style.background = on > 0 ? `color-mix(in srgb, var(--c-main) ${(16 * on).toFixed(1)}%, var(--c-card))` : "";
          el.style.boxShadow = on > 0 ? `inset 0 0 0 1.5px color-mix(in srgb, var(--c-main) ${(45 * on).toFixed(1)}%, var(--c-line)),0 14px 30px -18px color-mix(in srgb,var(--c-ink) 50%,transparent)` : "";
          ic.el.style.background = on > 0 ? `color-mix(in srgb, var(--c-main) ${(100 * on).toFixed(1)}%, transparent)` : "transparent";
        }
        ic.el.style.boxShadow = `inset 0 0 0 ${(2 * (1 - on)).toFixed(2)}px var(--c-line)`;
        ic.path.style.strokeDashoffset = (1 - seg(t, tl + 0.06, 0.28)).toFixed(3);
      });
    });
    note("pills", at, (items.length - 1) * gap + 0.3);
    return root;
  };

  // ======================= 代码块 =======================
  // hz.k.code(par, 行[], {title 文件名, t0 出现(只用于记账,出场自己用 T.pop/panel), typeAt 逐字开始(省略 = 直接全显), cps=30,
  //   hl:[{line 行号(从 1 起)或 [起,止], at, d=0.35}], light 浅色版, num=true 行号, size 字号(默认 24), w, x, y})
  // 一行 = "文字" 或 [["文字","k|s|n|c"], ...](k 关键字 s 字符串 n 数字 c 注释)
  // 返回根元素;root.line(行号) → 该行在根元素里的 {x,y,w,h},可直接交给 hz.k.frame / pulse 框住某一行
  K.code = (par, lines, o = {}) => {
    const root = ui(mk("div", "hz-k-code" + (o.light ? " light" : ""), par)); place(root, o);
    if (o.w) root.style.width = o.w + "px";
    if (o.size) root.style.setProperty("--k-fs", o.size + "px");
    mk("div", "hd", root, "", `<i></i><i></i><i></i><span>${esc(o.title || "")}</span>`);
    const bd = mk("div", "bd", root), cps = o.cps ?? 30, chars = [], LN = [];
    lines.forEach((ln, i) => {
      const row = mk("div", "ln", bd), hlb = mk("div", "hl", row);
      if (o.num !== false) mk("span", "no", row, "", String(i + 1));
      const cd = mk("span", "cd", row);   // 语法色类名加 t- 前缀:hz.css 有全局 .c{position:absolute}
      (typeof ln === "string" ? [[ln]] : ln).forEach(([s, c]) => { const g = mk("span", c ? "t-" + c : "", cd); [...s].forEach((ch) => { const e = mk("span", "", g); e.textContent = ch; chars.push({ e, i }); }); });
      LN.push({ row, hlb, cd });
    });
    const T0 = o.typeAt, cr = T0 == null ? null : mk("span", "cr", null);
    // 每行打完的时刻(检查器用);没打字的直接用 t0
    const done = lines.map(() => o.t0 ?? 0);
    if (T0 != null) chars.forEach((c, k) => (done[c.i] = T0 + (k + 1) / cps));
    LN.forEach((l, i) => mark(l.cd, done[i]));
    const HL = (o.hl || []).map((q) => ({ a: Array.isArray(q.line) ? q.line[0] : q.line, b: Array.isArray(q.line) ? q.line[1] : q.line, at: q.at, d: q.d ?? 0.35 }));
    hz.every((t) => {
      if (T0 != null) {
        const n = cl(Math.floor((t - T0) * cps), 0, chars.length);
        chars.forEach((c, k) => (c.e.style.visibility = k < n ? "" : "hidden"));
        const ref = n > 0 ? chars[n - 1].e : null;   // 光标跟在最后一个已出现的字后面
        if (ref) { if (ref.nextSibling !== cr) ref.after(cr); } else if (LN[0].cd.firstChild !== cr) LN[0].cd.prepend(cr);
        const tEnd = T0 + chars.length / cps;
        cr.style.opacity = t < T0 - 0.2 ? 0 : t < tEnd ? 1 : Math.floor((t - tEnd) * 2.2) % 2 ? 0 : 1;
      }
      LN.forEach((l, i) => { let v = 0; for (const q of HL) if (i + 1 >= q.a && i + 1 <= q.b) v = Math.max(v, stop()(seg(t, q.at, q.d))); l.hlb.style.transform = `scaleX(${v.toFixed(4)})`; });
    });
    root.line = (n) => { const r = LN[n - 1].row; return { x: 0, y: bd.offsetTop + r.offsetTop, w: root.offsetWidth, h: r.offsetHeight }; };
    if (T0 != null) note("code", T0, chars.length / cps);
    HL.forEach((q) => note("hl", q.at, q.d));
    return root;
  };

  // ======================= 面板滑入 =======================
  // hz.k.panel(el, t0, {from:"r"|"l"|"b"|"t", dist=140, d=0.55, t1 滑出时刻}) —— 出场动画,不计入交互
  K.panel = (el, t0, o = {}) => {
    const dist = o.dist ?? 140, d = o.d ?? 0.55, t1 = o.t1 ?? 1e9, f = o.from || "r";
    const [ux, uy] = { r: [1, 0], l: [-1, 0], b: [0, 1], t: [0, -1] }[f];
    hz.every((t) => {
      const u = seg(t, t0, d), v = stop()(u), x = seg(t, t1, d * 0.8), xv = E.in(x);
      const k = (1 - v) + xv;
      el.style.visibility = u > 0 && x < 1 ? "" : "hidden";
      el.style.opacity = (cl(u * 2.5) * (1 - cl(x * 1.6))).toFixed(3);
      el.style.translate = `${(ux * dist * k).toFixed(1)}px ${(uy * dist * k).toFixed(1)}px`;
      el.style.filter = k > 0.02 ? `blur(${(6 * Math.min(1, k)).toFixed(2)}px)` : "";
    });
    return el;
  };

  // ======================= 满幅暗场 =======================
  // hz.k.dark(sp, [[t0, t1], ...], {fin=0.35 淡入, fout=0.4 淡出, css 自定背景}) —— 铺在 sp.bg(屏幕空间,在所有 3D 图层后面),
  // 无论镜头怎么转都满幅,不会露纸底竖缝。返回元素;el.at(t) = 该时刻暗场浓度(0–1),可用来同步切换字色
  K.dark = (sp, spans, o = {}) => {
    const fin = o.fin ?? 0.35, fout = o.fout ?? 0.4;
    const el = mk("div", "hz-k-dark", sp.bg, o.css || "background:radial-gradient(ellipse 70% 65% at 50% 46%,color-mix(in srgb,var(--k-dark) 82%,var(--c-card)),var(--k-dark) 62%,color-mix(in srgb,var(--k-dark) 80%,#000) 100%)");
    el.at = (t) => spans.reduce((a, [a0, a1]) => Math.max(a, E.inout(seg(t, a0, fin)) * (1 - E.inout(seg(t, a1, fout)))), 0);
    hz.every((t) => { const a = el.at(t); el.style.opacity = a.toFixed(3); el.style.visibility = a > 0.001 ? "" : "hidden"; });
    return el;
  };

  // ======================= 给已有小部件记账 =======================
  const wrap = (obj, name, f) => { const fn = obj[name]; if (!fn) return; obj[name] = (...a) => { const r = fn(...a); f(r, ...a); return r; }; };
  wrap(hz.w, "terminal", (r, p, cmds, o = {}) => { ui(r); const a = cmds[0] && cmds[0].at != null ? cmds[0].at : o.t0 ?? 0; note("terminal", a, r.tDone - a); });
  wrap(hz.w, "spinner", (r, p, o = {}) => { if (o.t1 != null) note("load", o.t1, o.t1 - (o.t0 ?? o.t1)); });
  wrap(hz.w, "cursor", (r, p, keys) => keys.forEach((k) => k.click && note("click", k.click === true ? k.t + 0.06 : k.click)));
  wrap(hz.w, "list", (r, p, items, o = {}) => { ui(r); note("list", o.at ?? (o.t0 ?? 0) + 0.6, (items.length - 1) * (o.gap ?? 0.18)); });
  wrap(hz.w, "results", (r, p, rows, o = {}) => { ui(r); note("results", o.t0 ?? 0, (rows.length - 1) * (o.gap ?? 0.16)); });
  wrap(hz.w, "progress", (r, p, o = {}) => { ui(r); note("progress", o.keys ? o.keys[0].t : o.t0 ?? 0); });
  wrap(hz.w, "input", (r, p, o = {}) => { ui(r); if (o.at != null) note("input", o.at); });
  wrap(hz.w, "button", (r, p, o = {}) => [].concat(o.press ?? []).forEach((t) => note("click", t)));
  wrap(hz, "card", (r) => ui(r));
  wrap(hz.t, "count", (r, el, v0, v1, t0, d) => note("count", t0, d));
})();
