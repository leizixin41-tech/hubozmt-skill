# 3D 空间引擎速查(hz_3d.js + hz_type.js)

页面依次加载:`hz.css` `hz_3d.css` → `hz.js` `hz_canvas.js`(只为 `hz.mk/put`)`hz_ui3d.js`(只为 `hz.w.cursor` 等 UI 小部件)`hz_3d.js` `hz_type.js`;规范 v2 的期最后加 `hz_kit.js`(案例段动画库存:截图窗、框选、浏览器、代码块、前后对比、pills、暗场……参数表在 `规范/02_合成师_动画与素材库.md`)。
完整范例:`episodes/2026-10-24_dsh-pet-3d/03_scene.html`(开头的 `L / TX / TS / PET / line3` 几个小函数直接抄)。

## 空间
```js
const sp = hz.space({ W, H, persp: 1600, fps: 30, light: 0.5, vignette: 0.36, grain: 0.08, mblur: 0.16 });
```
- 世界坐标单位 ≈ 像素:摄像机距离 `dist = persp(1600)` 时,z=0 的图层 1:1 显示。z 正 = 靠近镜头。
- `sp.layer({x,y,z, rx,ry,rz, s, anchor:"c"|"l"|"r"|"tl", dof:true, css})` → 图层元素;内容放进 `.in`。`anchor:"l"` = 左边缘竖直居中对齐到该点(文字用),`"tl"` = 左上角(宠物/窗口用,内部自己定位)。
- `l.put(x,y,z)` 每帧移动图层;`l.filt` 额外滤镜(不要直接写 `l.style.filter`,景深会覆盖)。透明度、缩放写在 `l.in` 上。

## 机位(摄像机绑空对象)
```js
sp.shots([{ t: 到位时刻, d: 飞行秒数, at: [x,y,z] 空对象, dist, yaw, pitch(正=仰视), roll, focus, ap, ca, drift: {dist, yaw, …每秒}, e: 缓动, arc }]);
```
- 没写的参数沿用上一个机位。默认缓动 `hz.ease.stop`(缓动 + 急停)。飞行中按距离自动拉远(arc 0.22)。
- `focus` = 焦平面相对空对象往镜头方向移多少;`ap` = 景深强度(0 全清,教程段 6–8,常规 12–15)。
- **移焦**:两个机位 `at/dist/yaw` 相同、只改 `focus`(d 0.25–0.35)。
- `sp.aim(M, sx, sy, {dist,yaw,pitch})` → 让世界点 M 落在屏幕 (sx,sy) 的 `at`;`sp.place(时刻, sx, sy, dz)` → 屏幕点反推世界点(**先 `sp.shots` 再用**)。
- `sp.shake(t, 幅度, 秒)`、`sp.glitch(t, 秒, 强度)`。

## 文字 `hz.t`(简写 T)
- 出现 `T.in(el, "文字" | [["文字","css"],…], t0, {mode:"type"|"rise"|"blur"|"drop"|"slide"|"scatter", gap, d, cps, caretOff, caretColor, caretW, dx, dy, s0, spread})`;拆出的分组在 `el.groups`(给强调用)。自动加 `hz-txt` / `data-t0`,出场前整块隐藏。
- 消失 `T.out(el, t1, {mode:"blur"|"slide"|"up"|"wipe", d, dx})`。
- 强调(第一个参数传 `el.groups[i]`,不要传图层 `.in`):`T.marker` `T.fill` `T.tape({color,text,key,keyColor})` `T.under` `T.strike` `T.box` `T.brackets`。
- 元件:`T.chip(par, {dark, css})` → `.tx` 放字;`T.pop(el, t0, {s0, slide, dx, dy})`;`T.count(el, v0, v1, t0, d, {sep, suffix, suffixCss})`(要强调数字时对 `el.querySelector(".v")` 用)。

## 字体类(hz_3d.css)
`.f-song` 粗宋 900 · `.f-song7` 宋 700 · `.f-smiley` 得意黑 · `.f-brand` Bricolage 窄斜 · `.f-num` 数字 · `.f-sub` 英文斜体小字 · `.f-mono` · `.f-wk` 文楷 · `.tagm` 等宽全大写标签 · `.hz-chip`(纸片)· `.hz-doc`(纸面卡)。

## 宠物/图片序列
高清帧序列用范例里的 `hdPet` / `PET(o,x,y,z,s,seq)`(图层点 = 脚底),`HZ.seek` 外包一层等图片解码。

## 检查
`bin/hz check <本期>`:查出画、重叠、遮挡、展示不足(完整出现到被甩出画/虚掉 ≥0.6 秒)。景深把字虚到 >2px 也算「消失」。
