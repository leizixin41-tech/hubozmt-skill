# hz_ui3d.js —— 3D 衔接 + UI 交互小部件(写给合成师)

加载:在 `hz.js` 之后 `<script src="../../engine/web/hz_ui3d.js"></script>`。所有时间都是**绝对秒数**,画面由 `HZ.seek(t)` 定格。
示例页:`episodes/_test_fusion/B_ui3d.html`(卡片 dive→输入→按钮→转圈→结果→settle)、`B_widgets.html`(终端/进度/列表/光标)。

## 颜色(只认 CSS 变量,写在页面 `:root` 上)
`--c-bg` 背景 · `--c-ink` 正文 · `--c-mute` 次要字 · `--c-main` 主色(按钮/聚焦/进度) · `--c-accent` 成功(勾) · `--c-warn` 失败/警告 · `--c-card` 卡面 · `--c-line` 描边 · 可选 `--c-on-main` 按钮上的字色(默认 = `--c-ink`;浅色主题要设成白)。

## 排版检查约定
卡片根元素都有 class `hz-card` + `data-t0`(完整出现时刻;dive 后自动改成落位时刻);小部件里的文字元素都有 class `hz-txt`。

## 卡片与 3D 衔接
| 函数 | 用途 | 参数 |
|---|---|---|
| `hz.card(parent, o)` | 生成毛玻璃卡片,返回卡片元素,内容放 `card.body`(竖排、间距 18) | `w` 宽, `h` 高(可省=自适应), `x,y` 左上角, `title`, `sub` 右上小字, `icon` HTML, `appear` 出现时刻(省略=一直在), `t0` |
| `hz.dive(card, t0, o)` | 卡片从画布上平放→先轻按一下→立起、朝镜头飞到画面中央、放大到占画面 `fill`,带透视;投影/毛玻璃加深,背景压暗;之后持续缓慢漂移 | `fill`=0.8(占画面比例), `rx`=7 `ry`=-9 `rz`=0(最终角度°), `ox,oy` 相对画面中心偏移 px, `dim`=0.42 背景压暗, `dimBlur`=3 背景虚化 px, `drift`=1.4 漂移幅度°(0=不动), `peel`=16 立起时多仰的角度, `spring`=[0.78,0.84] 位移弹簧[响应秒,阻尼], `tilt`=[0.95,0.68] 角度弹簧, `persp`=1700, `cam`=true 时调用 `hz.camTo(card, t0-0.5, camOpts)` |
| `hz.settle(card, t0, o)` | 反向:卡片放平、缩小、落回原位(落地轻压一下),压暗撤掉 | `spring`=[0.7,0.86], `tilt`=[0.75,0.8], `cam` |

```js
const card = hz.card(world, { x: 700, y: 330, w: 620, title: "号码查询", sub: "Lookup" });
hz.dive(card, 0.8, { rx: 8, ry: -11 });   // 0.8s 起立,约 1.7s 落稳
hz.settle(card, 8.15);
```
注意:① 卡片本身**不要再用 `hz.track` 动 transform**(会打架),要动就套一层父元素;② 卡片可以放在 A 的无限画布世界里,dive 每帧量卡片在屏幕上的位置,镜头动也能对准;③ 压暗层插在卡片前面,并把卡片和祖先的 z-index 临时抬高;④ 同一张卡可以多次 dive/settle,按时间排好即可;⑤ 要设计按 dive 后的大小看:620 宽的卡在 1080p 下大约放大到 1.9 倍,所以卡里字号 18–28px 就够。

## UI 小部件 hz.w.*(都返回根元素;给 `x,y` 就绝对定位,否则按文档流排;`appear` = 淡入上浮的时刻)
| 函数 | 用途 | 主要参数 |
|---|---|---|
| `hz.w.input(parent, o)` | 输入框:聚焦描边弹出 → 逐字输入(字微上浮,节奏轻微不均)→ 光标停下后柔和闪烁 | `label`, `placeholder`, `text`, `at` 开始输入, `cps`=12 每秒字数, `focus`=at-0.35, `blur` 失焦时刻, `prefix`, `jitter:false` 匀速;返回元素的 `.tDone` = 打完时刻 |
| `hz.w.button(parent, o)` | 按钮:按下下沉缩小 → 弹簧回弹 + 波纹 | `label`, `icon` HTML, `press` 时刻或数组, `ripple`=true, `rx,ry` 波纹起点(0–1), `pill` 胶囊形, `h`, `resp`=0.42 `damp`=0.5 |
| `hz.w.spinner(parent, o)` | 加载转圈(弧长呼吸);结束时弧收满 → 变成绿色圆勾并轻弹 | `t0` 出现, `t1` 结束, `done`=true(false=结束时淡出), `size`=44, `text`, `doneText` |
| `hz.w.results(parent, rows, o)` | 结果行逐行弹出:勾弹出+画出,字段名-值,值右侧轻滑入 | rows=`[{k, v, ok, warn, color:"accent"}]`(ok:false 显示叉), `t0`, `gap`=0.16, `icon`=true |
| `hz.w.list(parent, items, o)` | 列表/网格逐项点亮打勾;`miss` 项灰掉、划线、显示「未找到」 | items=`["A", {label, miss, tag}]`, `cols`=1, `t0` 出现, `at` 开始点亮, `gap`=0.18, `missText` |
| `hz.w.terminal(parent, cmds, o)` | 终端窗口:逐条敲命令 → 回车 → 输出逐行出现,满了自动平滑上滚 | cmds=`[{cmd, at(可省=接上一条), cps(可省=整体 cps), out:["行", {s, ok, err}], enter=0.3, wait=0.25, gap=0.09, next=0.45}]`, `title`, `rows`=8 可见行, `cps`=22, `prompt`="$", `t0`;`.tDone` |
| `hz.w.progress(parent, o)` | 进度条(主色→成功色渐变 + 流光 + 百分比) | `label`, `t0,t1,from,to`,或 `keys:[{t,v}]` 做「卡一下再冲」, `pct`=true |
| `hz.w.cursor(parent, keys, o)` | 鼠标光标:弧线移动(带轻微倾斜),点击时缩一下 + 主色圆环 | keys=`[{t 到达时刻, x,y 或 el(+dx,dy 相对元素左上,默认中心), d=0.7 移动用时, click:true/时刻}]`, `t0` 出现, `t1` 消失, `size`=34 |

```js
const inp = hz.w.input(card.body, { label: "手机号码", placeholder: "输入号码", text: "+86 138 0013 8000", at: 2.05 });
const btn = hz.w.button(card.body, { label: "开始查询", press: 4.3 });
hz.w.cursor(card, [{ t: 3.6, x: 470, y: 260 }, { t: 4.24, el: btn, click: true }], { t1: 5.5 });   // 点击时刻 = 4.30,和按钮 press 对齐
hz.w.spinner(area, { t0: 4.45, t1: 5.55, text: "正在查询…", doneText: "查询完成" });
hz.w.results(area, [{ k: "归属地", v: "北京 · 中国移动" }, { k: "风险标记", v: "无", color: "accent" }], { t0: 6.15 });
hz.w.terminal(card.body, [{ cmd: "npm i ghosttrack", at: 1, out: [{ s: "✓ ready", ok: true }] }], { rows: 6 });
hz.w.progress(card.body, { label: "同步", keys: [{ t: 1, v: 0 }, { t: 2, v: 46 }, { t: 2.6, v: 52 }, { t: 3.4, v: 100 }] });
hz.w.list(card.body, ["GitHub", { label: "Reddit", miss: true }, "X"], { cols: 2, t0: 0.3, at: 1 });
```
小技巧:按钮点击要和光标点击同一时刻(光标 `click:true` = 到达后 +0.06s);转圈和结果叠在同一块固定高度的区域里(都 `position:absolute`),避免卡片高度跳。
