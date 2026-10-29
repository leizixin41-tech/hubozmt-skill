/* hz_3d.js —— 真 3D 空间(AE 式:摄像机绑空对象)
   - 所有素材/文字都是 3D 图层(sp.layer),按远近(z)分层;摄像机看向「空对象」at,绕它转(yaw/pitch/roll)、推拉(dist)。
   - 运镜 sp.shots([...]):每个机位一个到位时刻 t,手感默认「缓动 + 急停」(hz.ease.stop)。
   - 景深:对焦在机位的焦平面上,离焦平面越远越虚。运动模糊:镜头越快越糊(方向跟着画面运动)。
   - 后期:暗角、胶片颗粒、窗光、色差、故障(sp.glitch)。
   用法见 engine/web/SPACE3D.md。依赖 hz.js。 */
(function () {
  const hz = window.hz, cl = hz.clamp, lerp = hz.lerp, R = Math.PI / 180;
  const NS = "http://www.w3.org/2000/svg";
  hz.ease.stop = hz.bez(0.62, 0, 0.1, 1);      // 缓动 + 急停:起步柔,到位干脆
  hz.ease.stopSoft = hz.bez(0.5, 0, 0.16, 1);
  const mk = (tag, cls, par, css) => { const e = document.createElement(tag); if (cls) e.className = cls; if (css) e.style.cssText = css; if (par) par.appendChild(e); return e; };
  const hash = (n) => { const x = Math.sin(n * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); };

  hz.space = (o = {}) => {
    const W = o.W || innerWidth, H = o.H || innerHeight, P = o.persp || 1600;
    const FPS = o.fps || 30;
    // ---------- DOM ----------
    // post 比画面四周各大 12px:色差/模糊在边缘产生的色边落在画外
    const post = mk("div", "hz3-post", document.body, `position:absolute;left:-12px;top:-12px;width:${W + 24}px;height:${H + 24}px;overflow:hidden;background:var(--c-bg)`);
    const bg = mk("div", "hz3-bg", post, "position:absolute;inset:0");
    const stage = mk("div", "hz3-stage", post, `position:absolute;left:12px;top:12px;width:${W}px;height:${H}px;perspective:${P}px;perspective-origin:50% 50%`);
    const world = mk("div", "hz3-world", stage, "position:absolute;left:0;top:0;width:0;height:0;transform-style:preserve-3d;transform-origin:0 0");
    const hud = mk("div", "hz3-hud", post, `position:absolute;left:12px;top:12px;width:${W}px;height:${H}px;pointer-events:none;z-index:10`);
    const fx = mk("div", "hz3-fx", document.body, "position:absolute;left:0;top:0;width:" + W + "px;height:" + H + "px;pointer-events:none;z-index:9000;overflow:hidden");
    // 窗光(两道柔和斜光影,随镜头微动)
    const light = mk("div", "", fx, "position:absolute;left:-20%;top:-20%;width:140%;height:140%;mix-blend-mode:multiply;opacity:" + (o.light ?? 0.55) +
      ";background:linear-gradient(115deg,transparent 0 30%,rgba(60,50,40,.10) 36%,transparent 44%,transparent 52%,rgba(60,50,40,.08) 58%,transparent 66%);filter:blur(30px)");
    const vig = mk("div", "", fx, `position:absolute;inset:0;background:radial-gradient(ellipse 75% 70% at 50% 48%,transparent 52%,rgba(0,0,0,${o.vignette ?? 0.34}) 100%)`);
    const grain = mk("div", "", fx, "position:absolute;left:-256px;top:-256px;right:-256px;bottom:-256px;mix-blend-mode:overlay;opacity:" + (o.grain ?? 0.08));
    { const c = document.createElement("canvas"); c.width = c.height = 256; const g = c.getContext("2d"), d = g.createImageData(256, 256);
      for (let i = 0; i < d.data.length; i += 4) { const v = 128 + (hash(i * 0.37) - 0.5) * 255; d.data[i] = d.data[i + 1] = d.data[i + 2] = v; d.data[i + 3] = 255; }
      g.putImageData(d, 0, 0); grain.style.backgroundImage = `url(${c.toDataURL()})`; }
    // 后期滤镜:运动模糊 + 色差(+ 故障)
    const svg = document.createElementNS(NS, "svg"); svg.setAttribute("width", 0); svg.setAttribute("height", 0); svg.style.position = "absolute";
    const CA = (src) => `<feColorMatrix in="${src}" type="matrix" values="1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 1 0" result="r"/><feOffset class="cr" in="r" dx="1" result="ro"/>
      <feColorMatrix in="${src}" type="matrix" values="0 0 0 0 0 0 1 0 0 0 0 0 0 0 0 0 0 0 1 0" result="g"/>
      <feColorMatrix in="${src}" type="matrix" values="0 0 0 0 0 0 0 0 0 0 0 0 1 0 0 0 0 0 1 0" result="bb"/><feOffset class="cb" in="bb" dx="-1" result="bo"/>
      <feBlend in="ro" in2="g" mode="screen" result="rg"/><feBlend in="rg" in2="bo" mode="screen"/>`;
    svg.innerHTML = `<filter id="hz3a" x="0" y="0" width="100%" height="100%" color-interpolation-filters="sRGB"><feGaussianBlur class="mb" in="SourceGraphic" stdDeviation="0 0" edgeMode="duplicate" result="b"/>${CA("b")}</filter>
      <filter id="hz3g" x="0" y="0" width="100%" height="100%" color-interpolation-filters="sRGB"><feGaussianBlur class="mb" in="SourceGraphic" stdDeviation="0 0" edgeMode="duplicate" result="b0"/>
      <feTurbulence class="tb" type="fractalNoise" baseFrequency="0.0004 0.09" numOctaves="1" seed="2" result="n"/><feDisplacementMap class="dm" in="b0" in2="n" scale="0" xChannelSelector="R" yChannelSelector="B" result="b"/>${CA("b")}</filter>`;
    document.body.appendChild(svg);
    const F = { a: svg.querySelector("#hz3a"), g: svg.querySelector("#hz3g") };

    const sp = { W, H, P, post, bg, stage, world, hud, fx, layers: [], cam: null };
    // band = 焦平面前后各多少距离内完全清楚(同一层级的文字 + 素材都放进这个带里,一起清楚)
    const CAM0 = { x: 0, y: 0, z: 0, dist: P, yaw: 0, pitch: 0, roll: 0, focus: 0, ap: 14, ca: 0.4, band: 240 };
    let SH = [];
    const KEYS = ["x", "y", "z", "dist", "yaw", "pitch", "roll", "focus", "ap", "ca", "band"];

    // ---------- 机位 ----------
    // shot = {t 到位时刻, d 飞行秒数(默认 0.8), at:[x,y,z] 空对象位置, dist 摄像机离空对象距离(=P 时焦平面 1:1), yaw 左右转°, pitch 俯仰°(正 = 仰视),
    //         roll, focus 焦平面相对空对象前移的距离(正 = 更靠近镜头), ap 景深强度(0 = 全清), band 清晰带半宽(默认 240),
    //         ca 色差 px, drift {dist,yaw,pitch,x,y} 每秒漂移, e 缓动, arc 中途拉远比例}
    sp.shots = (list) => {
      SH = list.map((s, i) => {
        const q = Object.assign({}, s);
        if (q.at) { q.x = q.at[0]; q.y = q.at[1]; q.z = q.at[2] || 0; }
        q.d = q.d ?? 0.8; q.e = q.e || hz.ease.stop; q.drift = q.drift || {};
        return q;
      }).sort((a, b) => a.t - b.t);
      let prev = Object.assign({}, CAM0);
      SH.forEach((s) => { KEYS.forEach((k) => { if (s[k] == null) s[k] = prev[k]; }); prev = s; });
    };
    const held = (s, t) => { const o = {}; const dt = Math.max(0, t - s.t); KEYS.forEach((k) => (o[k] = s[k] + (s.drift[k] || 0) * dt)); return o; };
    const SHK = [];
    sp.shake = (t0, amp = 8, d = 0.35) => SHK.push({ t0, amp, d });
    function stateAt(t) {
      if (!SH.length) return Object.assign({}, CAM0);
      let i = 0; for (let k = 1; k < SH.length; k++) if (t >= SH[k].t - SH[k].d) i = k;
      const cur = SH[i];
      let st = held(cur, t);
      // 正在飞向 cur(t 在 cur.t-d .. cur.t 之间)
      if (i > 0 && t < cur.t) {
        const a = held(SH[i - 1], cur.t - cur.d), u = cl((t - (cur.t - cur.d)) / cur.d), e = cur.e(u);
        st = {}; KEYS.forEach((k) => (st[k] = lerp(a[k], cur[k], e)));
        const travel = Math.hypot(cur.x - a.x, cur.y - a.y, cur.z - a.z);
        const arc = cur.arc ?? 0.22; st.dist += Math.min(travel, 6000) * arc * Math.sin(Math.PI * e);
      }
      for (const s of SHK) { const u = (t - s.t0) / s.d; if (u < 0 || u > 1) continue; const k = s.amp * Math.pow(1 - u, 2), f = Math.floor(t * FPS);
        st.x += (hash(f) - 0.5) * 2 * k; st.y += (hash(f + 7) - 0.5) * 2 * k; st.roll += (hash(f + 3) - 0.5) * k * 0.12; }
      return st;
    }
    sp.stateAt = stateAt;
    // 世界点 → 屏幕
    function camSpace(s, p) {
      let x = p[0] - s.x, y = p[1] - s.y, z = (p[2] || 0) - s.z;
      const cy = Math.cos(s.yaw * R), sy = Math.sin(s.yaw * R); let x1 = x * cy + z * sy, z1 = -x * sy + z * cy;
      const cx = Math.cos(s.pitch * R), sx = Math.sin(s.pitch * R); let y1 = y * cx - z1 * sx, z2 = y * sx + z1 * cx;
      const cr = Math.cos(s.roll * R), sr = Math.sin(s.roll * R); const x2 = x1 * cr - y1 * sr, y2 = x1 * sr + y1 * cr;
      return [x2, y2, z2];
    }
    function project(s, p) { const c = camSpace(s, p), depth = s.dist - c[2], k = P / Math.max(1, depth); return { x: W / 2 + c[0] * k, y: H / 2 + c[1] * k, depth, k }; }
    sp.project = project;
    // 屏幕点(sx,sy)+ 相对空对象的深度 dz(正 = 靠近镜头)→ 世界点;s 可以是机位对象或时刻
    sp.place = (s, sx, sy, dz = 0) => {
      if (typeof s === "number") s = stateAt(s);
      const k = P / (s.dist - dz);
      let x = (sx - W / 2) / k, y = (sy - H / 2) / k, z = dz;
      const cr = Math.cos(-s.roll * R), sr = Math.sin(-s.roll * R); [x, y] = [x * cr - y * sr, x * sr + y * cr];
      const cx = Math.cos(-s.pitch * R), sx2 = Math.sin(-s.pitch * R); [y, z] = [y * cx - z * sx2, y * sx2 + z * cx];
      const cy = Math.cos(-s.yaw * R), sy3 = Math.sin(-s.yaw * R); [x, z] = [x * cy + z * sy3, -x * sy3 + z * cy];
      return [x + s.x, y + s.y, z + s.z];
    };
    // 让世界点 M 出现在屏幕 (sx,sy),返回空对象位置 at
    sp.aim = (M, sx, sy, s) => {
      const q = Object.assign({}, CAM0, s, { x: 0, y: 0, z: 0 });
      const off = sp.place(q, sx, sy, 0);
      return [M[0] - off[0], M[1] - off[1], (M[2] || 0) - off[2]];
    };

    // ---------- 图层 ----------
    // sp.layer({x,y,z, rx,ry,rz, s, anchor:"c"|"l"|"tl", dof:true|false|系数, css, cls, par}) → 元素;内容放进 .in(按 anchor 对齐到该点)
    //   dof:系数 = 这层虚化强度的倍数(背景淡字可给 1.5 更虚);false = 永远清楚
    sp.layer = (q = {}) => {
      const el = mk("div", "hz3-l" + (q.cls ? " " + q.cls : ""), q.par || world, "position:absolute;left:0;top:0;width:0;height:0;transform-style:flat");
      const a = q.anchor || "c";
      el.in = mk("div", "hz3-in", el, "position:absolute;left:0;top:0;" + (a === "c" ? "transform:translate(-50%,-50%);" : a === "l" ? "transform:translate(0,-50%);" : a === "r" ? "transform:translate(-100%,-50%);" : "") + (q.css || ""));
      el.p = [q.x || 0, q.y || 0, q.z || 0]; el.r = [q.rx || 0, q.ry || 0, q.rz || 0]; el.sc = q.s || 1; el.dof = q.dof ?? true; el.dofK = typeof q.dof === "number" ? q.dof : 1; el.extra = "";
      el.put = (x, y, z) => { el.p = [x, y, z ?? el.p[2]]; tf(el); };
      tf(el); if (!q.par) sp.layers.push(el);
      return el;
    };
    function tf(el) { el.style.transform = `translate3d(${el.p[0].toFixed(2)}px,${el.p[1].toFixed(2)}px,${el.p[2].toFixed(2)}px) rotateY(${el.r[1]}deg) rotateX(${el.r[0]}deg) rotateZ(${el.r[2]}deg) scale(${el.sc})` + el.extra; }
    sp.tf = tf;

    // ---------- 布景(可以整体转向) ----------
    // sp.set([x,y,z], {ry, rx}) → 布景:.w(局部点)→ 世界点;.layer({...局部坐标}) 建图层(自动带上布景朝向);
    //   .face({dyaw, dpitch}) → 正对这个布景的 yaw/pitch(在此基础上可再偏一点)。布景朝向不同,转场时镜头就必须转过去。
    sp.set = (o0, q0 = {}) => {
      const ry = q0.ry || 0, rx = q0.rx || 0;
      const S = { o: o0, ry, rx };
      S.w = (x, y, z = 0) => {
        const cx = Math.cos(rx * R), sx = Math.sin(rx * R);
        const y1 = y * cx - z * sx, z1 = y * sx + z * cx;
        const cy = Math.cos(ry * R), sy = Math.sin(ry * R);
        const x2 = x * cy + z1 * sy, z2 = -x * sy + z1 * cy;
        return [o0[0] + x2, o0[1] + y1, (o0[2] || 0) + z2];
      };
      S.layer = (q = {}) => { const p = S.w(q.x || 0, q.y || 0, q.z || 0);
        return sp.layer(Object.assign({}, q, { x: p[0], y: p[1], z: p[2], rx: (q.rx || 0) + rx, ry: (q.ry || 0) + ry })); };
      S.face = (q = {}) => ({ yaw: -ry + (q.dyaw || 0), pitch: -rx + (q.dpitch || 0) });
      return S;
    };

    // ---------- 故障 ----------
    const GL = [];
    sp.glitch = (t0, d = 0.16, amt = 1) => GL.push({ t0, d, amt });

    // ---------- 每帧 ----------
    const mb = [...svg.querySelectorAll(".mb")], cr = [...svg.querySelectorAll(".cr")], cb = [...svg.querySelectorAll(".cb")];
    const tb = svg.querySelector(".tb"), dm = svg.querySelector(".dm");
    hz.every((t) => {
      const s = stateAt(t), s0 = stateAt(t - 1 / FPS); sp.cam = s;
      world.style.transform = `translate3d(${W / 2}px,${H / 2}px,0) translateZ(${(P - s.dist).toFixed(2)}px) rotateZ(${s.roll.toFixed(3)}deg) rotateX(${s.pitch.toFixed(3)}deg) rotateY(${s.yaw.toFixed(3)}deg) translate3d(${(-s.x).toFixed(2)}px,${(-s.y).toFixed(2)}px,${(-s.z).toFixed(2)}px)`;
      // 景深 + 剔除
      const fd = s.dist - s.focus;
      for (const el of sp.layers) {
        if (el.hidden3) { el.style.visibility = "hidden"; continue; }
        const q = project(s, el.p), off = q.depth < 80 || Math.abs(q.x - W / 2) > W * 1.6 || Math.abs(q.y - H / 2) > H * 1.9;
        el.style.visibility = off ? "hidden" : "";
        if (off) continue;
        const b = el.dof && s.ap > 0 ? Math.min(16, el.dofK * s.ap * Math.max(0, Math.abs(q.depth - fd) - s.band) / q.depth) : 0;
        const f = (b > 0.35 ? `blur(${b.toFixed(2)}px)` : "") + (el.filt ? " " + el.filt : "");
        el.style.filter = f || "";
      }
      // 运动模糊(参考点在屏幕上的位移)
      let vx = 0, vy = 0;
      for (const d of [[0, 0, 0], [500, 0, 0], [-500, 0, 0], [0, 350, 0], [0, -350, 0], [0, 0, -900]]) {
        const p = [s.x + d[0], s.y + d[1], s.z + d[2]], a = project(s, p), b = project(s0, p);
        vx += Math.abs(a.x - b.x); vy += Math.abs(a.y - b.y);
      }
      vx /= 6; vy /= 6;
      const bx = Math.min(24, vx * (o.mblur ?? 0.18)), by = Math.min(24, vy * (o.mblur ?? 0.18));
      let ca = s.ca, g = null;
      for (const q of GL) { const u = (t - q.t0) / q.d; if (u >= 0 && u <= 1) g = q; }
      const f = Math.floor(t * FPS);
      if (g) {
        const u = (t - g.t0) / g.d, k = g.amt * Math.sin(Math.PI * u);
        ca += 7 * k; tb.setAttribute("seed", 1 + (f % 97)); tb.setAttribute("baseFrequency", `0.0004 ${(0.05 + 0.08 * hash(f)).toFixed(3)}`); dm.setAttribute("scale", (60 * k * (0.5 + hash(f + 5))).toFixed(1));
      }
      ca += Math.min(4, (bx + by) * 0.08);
      mb.forEach((m) => m.setAttribute("stdDeviation", `${bx.toFixed(2)} ${by.toFixed(2)}`));
      cr.forEach((m) => m.setAttribute("dx", ca.toFixed(2))); cb.forEach((m) => m.setAttribute("dx", (-ca).toFixed(2)));
      post.style.filter = g ? "url(#hz3g)" : (bx + by > 0.3 || ca > 0.2 ? "url(#hz3a)" : "");
      // 颗粒每帧换位置;窗光随镜头微动
      grain.style.transform = `translate(${Math.floor(hash(f) * 256)}px,${Math.floor(hash(f + 1) * 256)}px)`;
      light.style.transform = `translate(${(-s.yaw * 9 - s.x * 0.02).toFixed(1)}px,${(s.pitch * 6 - s.y * 0.015).toFixed(1)}px)`;
    });
    return sp;
  };
})();
