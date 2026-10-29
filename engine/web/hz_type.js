/* hz_type.js —— 文字动效库(从胡泊系列参考视频拆出来的那套):
   出现:type 打字机+粗光标 / rise 逐字上浮去虚 / blur 原地去虚 / scatter 随机散字显影 / slide 带运动模糊滑入急停 / drop 砸下
   强调:marker 荧光笔扫底 / tape 黑胶带擦过反白 / under 下划线 / strike 删除线 / box 描框 / brackets 「」角标 / fill 色块垫底
   消失:out(blur 虚化 / slide 运动模糊滑走 / up 上飘 / wipe 擦除)
   元件:chip 纸片标签(圆点+粗宋)、sub 中文下的英文小字
   所有函数第一个参数是元素;parts = "文字" 或 [["文字", "css"], ...]。完整出现的时刻会写进 data-t0(检查器用)。 */
(function () {
  const hz = window.hz, cl = hz.clamp, lerp = hz.lerp, E = hz.ease;
  const stop = () => E.stop || E.out;
  const mk = (tag, cls, par, css, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (css) e.style.cssText = css; if (html != null) e.innerHTML = html; if (par) par.appendChild(e); return e; };
  const seg = (t, a, d) => cl((t - a) / d);
  const hash = (n) => { const x = Math.sin(n * 91.7 + 13.1) * 43758.5453; return x - Math.floor(x); };
  const T = (hz.t = {});
  const mark = (el, t) => { el.classList.add("hz-txt"); el.dataset.t0 = (+t).toFixed(3); return el; };
  T.mark = mark;
  // 拆字:返回 [{span, part}]
  function split(el, parts) {
    el.innerHTML = ""; if (typeof parts === "string") parts = [[parts]];
    const out = [];
    parts.forEach(([s, css], pi) => {
      const g = mk("span", "hz-tp", el, css || ""); g.style.whiteSpace = "pre";
      [...s].forEach((c) => { const sp = mk("span", "hz-c", g, "display:inline-block;white-space:pre"); sp.textContent = c; out.push({ sp, pi, g }); });
    });
    el.groups = [...el.querySelectorAll(":scope > .hz-tp")];
    return out;
  }
  T.split = split;
  // 方向性运动模糊(每个元素一个 SVG 滤镜)
  let FID = 0, DEFS = null;
  function mblur(el) {
    if (!DEFS) { const s = document.createElementNS("http://www.w3.org/2000/svg", "svg"); s.setAttribute("width", 0); s.setAttribute("height", 0); s.style.position = "absolute"; document.body.appendChild(s); DEFS = s; }
    const id = "hzmb" + FID++; const f = document.createElementNS("http://www.w3.org/2000/svg", "filter");
    f.setAttribute("id", id); f.setAttribute("x", "-50%"); f.setAttribute("y", "-50%"); f.setAttribute("width", "200%"); f.setAttribute("height", "200%");
    f.innerHTML = '<feGaussianBlur stdDeviation="0 0"/>'; DEFS.appendChild(f);
    const g = f.firstChild; return (bx, by) => { g.setAttribute("stdDeviation", `${Math.max(0, bx).toFixed(2)} ${Math.max(0, by).toFixed(2)}`); return bx + by > 0.2 ? `url(#${id})` : ""; };
  }
  T.mblur = mblur;

  // ---------- 出现 ----------
  // o: gap 字间隔, d 每字时长, mode, cps(type), caret, caretOff, caretColor, dx/dy(slide,px), spread(scatter), s0(drop 起始缩放)
  T.in = (el, parts, t0, o = {}) => {
    const mode = o.mode || "rise", ch = split(el, parts), n = ch.length;
    let end = t0;
    if (mode === "type") {
      const cps = o.cps || 16, caret = o.caret !== false;
      const cr = caret ? mk("span", "hz-caret", el, `display:inline-block;width:${o.caretW || "0.07em"};height:1.02em;margin-left:0.06em;vertical-align:-0.1em;background:${o.caretColor || "currentColor"}`) : null;
      end = t0 + n / cps; const off = o.caretOff ?? end + 0.9;
      hz.every((t) => {
        const k = t < t0 ? 0 : Math.min(n, Math.floor((t - t0) * cps) + 1);
        ch.forEach((c, i) => (c.sp.style.visibility = i < k ? "" : "hidden"));
        if (cr) { const on = t >= t0 - 0.25 && t < off; cr.style.opacity = !on ? 0 : (t < end ? 1 : (Math.floor((t - end) * 2.2) % 2 ? 0 : 1)); }
        el.style.visibility = t < t0 - 0.25 ? "hidden" : "";
      });
    } else if (mode === "slide") {
      hz.every((t) => { if (t < t0 - 0.02) el.style.visibility = "hidden"; else if (el.style.visibility === "hidden" && !el._gone) el.style.visibility = ""; });
      const d = o.d ?? 0.5, dx = o.dx ?? -260, dy = o.dy ?? 0, mb = mblur(el), e = stop();
      end = t0 + d;
      hz.every((t) => {
        if (t < t0) { el.style.opacity = 0; return; }
        const u = seg(t, t0, d), v = e(u), du = (e(cl(u + 0.02)) - v) / 0.02 / d;
        el.style.opacity = cl(u * 4); el.style.translate = `${(dx * (1 - v)).toFixed(1)}px ${(dy * (1 - v)).toFixed(1)}px`;
        el.style.filter = mb(Math.abs(dx) * du * 0.03, Math.abs(dy) * du * 0.03);
      });
    } else {
      const gap = o.gap ?? (mode === "scatter" ? 0 : 0.045), d = o.d ?? (mode === "drop" ? 0.32 : 0.5), spread = o.spread ?? 0.4;
      const order = ch.map((c, i) => (mode === "scatter" ? hash(i + n * 3.3) * spread : i * gap));
      end = t0 + Math.max(...order, 0) + d;
      const e = stop();
      hz.every((t) => {
        // 出场前整块隐藏(不然透明的字也会挡住别的元素)
        if (t < t0 - 0.02) el.style.visibility = "hidden"; else if (el.style.visibility === "hidden" && !el._gone) el.style.visibility = "";
        ch.forEach((c, i) => {
          const u = seg(t, t0 + order[i], d), v = e(u), s = c.sp.style;
          if (u <= 0) { s.opacity = 0; return; }
          s.opacity = mode === "scatter" ? cl(u * 1.6) : cl(u * 2.2);
          if (mode === "rise") { s.translate = `0 ${(0.38 * (1 - v)).toFixed(3)}em`; s.filter = v < 0.98 ? `blur(${(7 * (1 - v)).toFixed(2)}px)` : ""; }
          else if (mode === "blur") { s.scale = lerp(1.12, 1, v).toFixed(4); s.filter = v < 0.98 ? `blur(${(14 * (1 - v)).toFixed(2)}px)` : ""; }
          else if (mode === "scatter") { s.filter = v < 0.98 ? `blur(${(10 * (1 - v)).toFixed(2)}px)` : ""; s.translate = `${((hash(i) - 0.5) * 0.4 * (1 - v)).toFixed(3)}em ${((hash(i + 9) - 0.5) * 0.4 * (1 - v)).toFixed(3)}em`; }
          else if (mode === "drop") { s.scale = lerp(o.s0 ?? 1.6, 1, v).toFixed(4); s.filter = v < 0.98 ? `blur(${(6 * (1 - v)).toFixed(2)}px)` : ""; }
        });
      });
    }
    mark(el, end); el._end = end; return el;
  };
  // ---------- 消失 ----------
  T.out = (el, t1, o = {}) => {
    const mode = o.mode || "blur", d = o.d ?? 0.3, mb = mode === "slide" ? mblur(el) : null, dx = o.dx ?? 320;
    hz.every((t) => {
      if (t < t1) return; const u = seg(t, t1, d), v = (mode === "slide" ? E.in : E.inout)(u);
      if (mode === "blur") { el.style.opacity = (1 - v).toFixed(3); el.style.filter = `blur(${(12 * v).toFixed(2)}px)`; }
      else if (mode === "slide") { el.style.opacity = (1 - cl((u - 0.5) * 2)).toFixed(3); el.style.translate = `${(dx * v).toFixed(1)}px 0`; el.style.filter = mb(Math.abs(dx) * v * 0.06, 0); }
      else if (mode === "up") { el.style.opacity = (1 - v).toFixed(3); el.style.translate = `0 ${(-40 * v).toFixed(1)}px`; el.style.filter = `blur(${(6 * v).toFixed(2)}px)`; }
      else if (mode === "wipe") { el.style.clipPath = `inset(0 0 0 ${(v * 100).toFixed(2)}%)`; }
      el._gone = u >= 1; if (u >= 1) el.style.visibility = "hidden";
    });
    return el;
  };
  // ---------- 强调 ----------
  const under = (tg, css) => { tg.style.position = "relative"; tg.style.display = tg.style.display || "inline-block"; return mk("span", "hz-fx", tg, "position:absolute;pointer-events:none;" + css); };
  // 荧光笔扫底(色块从左扫到右,垫在字下面)
  T.marker = (tg, t0, o = {}) => {
    const b = under(tg, `left:-0.06em;right:-0.06em;top:${o.top ?? "0.14em"};bottom:${o.bottom ?? "0.02em"};background:${o.color || "var(--c-mark)"};z-index:-1;transform-origin:0 50%;transform:scaleX(0)` + (o.skew ? `;skew:${o.skew}deg 0` : ""));
    tg.style.zIndex = 0; tg.style.isolation = "isolate";
    hz.every((t) => { b.style.transform = `scaleX(${stop()(seg(t, t0, o.d ?? 0.32)).toFixed(4)})`; });
    return b;
  };
  T.fill = (tg, t0, o = {}) => T.marker(tg, t0, Object.assign({ top: "-0.06em", bottom: "-0.08em", d: 0.28 }, o));
  // 黑胶带擦过:色条扫过,条下面的字反白(关键词可另给颜色)
  T.tape = (tg, t0, o = {}) => {
    tg.style.position = "relative"; tg.style.display = "inline-block";
    const cv = mk("span", "hz-fx", tg, `position:absolute;left:-0.12em;right:-0.12em;top:-0.04em;bottom:-0.1em;background:${o.color || "var(--c-ink)"};pointer-events:none;clip-path:inset(0 100% 0 0)`);
    const cp = mk("span", "hz-fx", tg, `position:absolute;left:0;top:0;white-space:pre;color:${o.text || "var(--c-card)"};pointer-events:none;clip-path:inset(0 100% 0 0)`);
    cp.innerHTML = [...tg.childNodes].filter((n) => n !== cv && n !== cp).map((n) => (n.outerHTML ?? n.textContent)).join("");
    cp.querySelectorAll(".hz-c").forEach((c) => { c.style.opacity = 1; c.style.filter = ""; c.style.translate = ""; c.style.visibility = ""; });
    if (o.key) cp.querySelectorAll(".hz-tp").forEach((g, i) => { if (o.key.includes(i)) g.style.color = o.keyColor || "var(--c-accent)"; });
    hz.every((t) => { const v = stop()(seg(t, t0, o.d ?? 0.4)), c = `inset(0 ${((1 - v) * 100).toFixed(2)}% 0 0)`; cv.style.clipPath = c; cp.style.clipPath = `inset(0 ${((1 - v) * 100).toFixed(2)}% 0 -0.2em)`; });
    return cv;
  };
  T.under = (tg, t0, o = {}) => { const b = under(tg, `left:0;right:0;bottom:${o.y ?? "-0.06em"};height:${o.h ?? "0.07em"};border-radius:99px;background:${o.color || "var(--c-main)"};transform-origin:0 50%;transform:scaleX(0)`);
    hz.every((t) => { b.style.transform = `scaleX(${stop()(seg(t, t0, o.d ?? 0.35)).toFixed(4)})`; }); return b; };
  T.strike = (tg, t0, o = {}) => { const b = under(tg, `left:-0.04em;right:-0.04em;top:52%;height:${o.h ?? "0.07em"};border-radius:99px;background:${o.color || "var(--c-ink)"};transform-origin:0 50%;transform:scaleX(0)`);
    hz.every((t) => { b.style.transform = `scaleX(${stop()(seg(t, t0, o.d ?? 0.3)).toFixed(4)})`; }); return b; };
  // 描框(细线从一角画满)
  T.box = (tg, t0, o = {}) => { const b = under(tg, `left:-0.18em;right:-0.18em;top:-0.1em;bottom:-0.14em;border:${o.w || 3}px solid ${o.color || "var(--c-accent)"};border-radius:${o.r || 4}px;clip-path:inset(0 100% 100% 0)`);
    hz.every((t) => { const v = stop()(seg(t, t0, o.d ?? 0.4)); b.style.clipPath = `inset(0 ${((1 - v) * 100).toFixed(1)}% ${((1 - cl(v * 1.6 - 0.3)) * 100).toFixed(1)}% 0)`; }); return b; };
  // 「 」角标:两个直角从中间向两边张开
  T.brackets = (tg, t0, o = {}) => {
    const w = o.w || 3, c = o.color || "var(--c-ink)", s = o.size || "0.38em", pad = o.pad || "0.28em";
    const a = under(tg, `left:-${pad};top:-0.12em;width:${s};height:${s};border-left:${w}px solid ${c};border-top:${w}px solid ${c}`);
    const b = under(tg, `right:-${pad};bottom:-0.12em;width:${s};height:${s};border-right:${w}px solid ${c};border-bottom:${w}px solid ${c}`);
    hz.every((t) => { const v = stop()(seg(t, t0, o.d ?? 0.4)); a.style.opacity = b.style.opacity = cl(v * 3);
      a.style.translate = `calc((1 - ${v.toFixed(4)}) * ${o.from || "1.2em"}) calc((1 - ${v.toFixed(4)}) * 0.3em)`; b.style.translate = `calc((${v.toFixed(4)} - 1) * ${o.from || "1.2em"}) calc((${v.toFixed(4)} - 1) * 0.3em)`; });
    return [a, b];
  };
  // ---------- 元件 ----------
  // 纸片标签:圆点 + 粗宋;返回元素,文字放在 .tx(用 T.in 显影)
  T.chip = (par, o = {}) => {
    const e = mk("div", "hz-chip" + (o.dark ? " dark" : ""), par, o.css || "");
    if (o.dot !== false) mk("i", "dot", e);
    e.tx = mk("span", "tx", e);
    return e;
  };
  // 外层整体出现(纸片、卡片):散字之外,卡片本身从虚到实 + 轻微放大急停
  T.pop = (el, t0, o = {}) => { const d = o.d ?? 0.4, mb = o.slide ? mblur(el) : null, dx = o.dx ?? 0, dy = o.dy ?? 0;
    hz.every((t) => { if (t < t0) { el.style.opacity = 0; el.style.visibility = "hidden"; return; } if (el.style.visibility === "hidden" && !el._gone) el.style.visibility = ""; const u = seg(t, t0, d), v = stop()(u);
      el.style.opacity = cl(u * 3); el.style.scale = lerp(o.s0 ?? 0.92, 1, v).toFixed(4); el.style.translate = `${(dx * (1 - v)).toFixed(1)}px ${(dy * (1 - v)).toFixed(1)}px`;
      el.style.filter = mb ? mb(Math.abs(dx) * (1 - v) * 0.08, Math.abs(dy) * (1 - v) * 0.08) : (v < 0.98 ? `blur(${(8 * (1 - v)).toFixed(2)}px)` : ""); }); return el; };
  // 数字滚动(到 v1,带千分位/后缀)
  T.count = (el, v0, v1, t0, d, o = {}) => { el.innerHTML = '<span class="v"></span>' + (o.suffix ? `<span class="sfx" style="${o.suffixCss || ""}">${o.suffix}</span>` : ""); const v = el.querySelector(".v");
    hz.every((t) => { const u = (o.e || stop())(seg(t, t0, d)), x = lerp(v0, v1, u); v.textContent = o.sep ? Math.round(x).toLocaleString("en-US") : Math.round(x); el.style.opacity = t < t0 - 0.1 ? 0 : 1; });
    mark(el, t0 + d); return el; };
})();
