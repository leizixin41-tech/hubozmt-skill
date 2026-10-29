# hz_canvas.js 速查(无限画布 + 文字动效)

在 `hz.js` 之后加载:`<script src="../../engine/web/hz.js"></script><script src="../../engine/web/hz_canvas.js"></script>`。
时间一律是**成片绝对秒**;缓动传 `hz.ease.*`(新增 `hz.ease.expo`=老引擎 E_EXPO、`out2`=E_OUT、`inout2`=E_INOUT)或 `hz.spring(响应秒, 阻尼)`。
完整范例:`episodes/_test_fusion/A_canvas.html`。

## 颜色(只用 CSS 变量)
在页面 `:root` 定义:`--c-bg` 底色、`--c-ink` 主文字、`--c-mute` 次要灰、`--c-main` 主色、`--c-accent` 辅助色、`--c-warn` 警示色。没定义时用内置的深色默认值。
函数里的颜色参数也写变量,例如 `{ color: "var(--c-accent)" }`。

## 无限画布
| 函数 | 用途 |
|---|---|
| `hz.canvas(world, nodes, o)` | 整片放在一张画布上,镜头按时间在节点间飞;讲过的节点虚化+压暗+降饱和+后退 |
| `hz.camTo(目标, t0, o)` | 镜头飞到某个元素(或世界矩形)把它推满屏,供「扎进卡片」 |
| `hz.put(父, x, y, o)` | 在节点里以 (x,y) 为中心放一个元素(`o.cls` 类名、`o.html` 内容、`o.z` 视差层、`o.css`) |
| `hz.cam` | 当前镜头 `{x, y, z(缩放), rx, ry(倾斜角), i(当前节点序号)}`,每帧更新 |

**节点参数** `{el, x, y, t, ...}`:
- `el` 节点容器(空 div,里面的元素用相对节点中心的坐标);`x, y` 世界坐标;`t` 镜头**到位**时刻。
- `zoom=1`;`flight=0.75` 飞行秒数(首节点自动 0.01);`pre=0.75`(在 `t - flight*pre` 起飞);`e` 飞行缓动(默认 expo,快起慢停,中途自动略拉远)。
- `drift=[每秒缩放, 每秒dx, 每秒dy]` 段内漂移,默认 `[0.01,0,0]`(缓慢推近)。
- `keys=[{t0, t1, x, y, zoom, rx, ry, e}]` 段内推镜/倾斜:到 t1 时镜头移到相对节点中心的 (x,y)、缩放倍数 zoom、倾斜 rx/ry(度),依次累积。
- `rx, ry` 本段静止时的画布倾斜;`tilt={rx, ry}` **飞进本节点途中**整张画布倾斜(飞到一半最大,落位归零)。
- `fade=1` 退后强度(0 不虚化,2 加倍);`z` 节点视差层(正数更近、移动更快);`lead=1` 提前几秒显示;`t1` 到点隐藏。
- `blob={c, r=900, a=0.12, dx, dy}`(可为数组)身后彩色光斑,镜头飞到本节点时渐亮、离开时渐暗。
- 节点内元素加 `data-z`(或 `hz.put` 的 `o.z`)就有独立视差。

**画布选项** `o`:`W, H`(默认窗口大小)、`persp=1800` 透视距离、`ramp=0.8` 退后过渡秒数、`dip=0.04` 飞行中额外拉远、`parallax=0.06` 每层视差。

**camTo 选项**:`d=0.8` 飞行秒数、`fill=0.72` 目标占画面比例、`t1` 返回时刻(不填就一直停在目标)、`back=0.8` 返回秒数、`rx/ry` 到位时倾斜、`dx/dy` 偏移、`zmul` 再放大倍数、`freeze=true`(首次量好尺寸就固定;false 则每帧追踪元素)。目标也可以是 `{x, y, w, h}` 世界矩形。

```js
const W = hz.$("#world"), a = hz.mk("div", "", W), b = hz.mk("div", "", W);
hz.fx.rise(hz.put(a, 0, 0, { cls: "big" }), "无限画布", 0.4);
const card = hz.put(b, 300, 0, { cls: "card", z: 1 });
hz.canvas(W, [
  { el: a, x: 0, y: 0, t: 0, blob: { c: "var(--c-main)" } },
  { el: b, x: 1400, y: 500, t: 3, tilt: { rx: 16, ry: -24 }, keys: [{ t0: 3.2, t1: 4.5, zoom: 1.1 }] },
]);
hz.camTo(card, 5, { d: 0.8, fill: 0.8, t1: 6.5 });
hz.cinemaBg("#bg");   // 背景放在 #world 前面的 div;必须在 hz.canvas 之后调用,才能跟上镜头
hz.start(8);
```

## 文字动效 `hz.fx.*`
目标元素 `el` 是已有元素(常用 `hz.put` 放);函数会写入内容、自动加 class `hz-txt` 和 `data-t0`(完整出现时刻,供排版检查)。字号、字体由 `el` 的 CSS 决定,动效尺寸都按 em 自动缩放。

| 函数 | 用途 | 主要参数(o) |
|---|---|---|
| `fx.rise(el, 文字, t0, o)` | 逐字上浮,模糊变清,逐字错开 | `gap=0.06` 逐字间隔、`d=0.8` 每字时长、`dy=0.32`(em)、`blur=0.09`(em)、`s0=1` 起始缩放、`dx`、`e`、`grad=true` 奶白渐变字(false 用纯 --c-ink) |
| `fx.caret(el, 文字, t0, o)` | 竖光标从左滑到右,字随之显现 | `d=0.75`、`e`、`soft=0.12` 边缘柔化、`color` 光标色(默认 --c-main)、`hold=0.25` 光标停留、`grad` |
| `fx.type(el, 文字, t0, o)` | 打字 + 闪烁光标;可打完删掉换新词 | `gap=0.065`、`delAt` 开始删除时刻、`delGap=0.035`、`next` 新词、`nextGap`、`pause=0.18`、`caretOff` 光标消失时刻、`caret=false` 不要光标、`fixed` 预留整行宽度(居中时不跳)、`grad` |
| `fx.odo(el, 数值, t0, o)` | 里程表式逐位滚动(低位连续滚,高位进位时滚) | `d=1.6`、`e`(默认 expo)、`sep=","` 千分位(""=不要)、`decimals`、`prefix`、`suffix`(如 "+"、"K")、`zeros=true` 显示前导 0(默认隐藏)、`grad=true` |
| `fx.hl(el, t0, o)` | 荧光笔:字后/字下一道笔触从左刷到右(el 是已有文字,可叠在 rise/caret 之后) | `mode="behind"`(字后半高色带)/`"under"`(字下细线)、`color`(默认 --c-main)、`d=0.55`、`a` 不透明度、`h` 粗细(em) |
| `fx.pill(el, 文字, t0, o)` | 胶囊标签弹簧弹出 | `color` 圆点和描边色、`dot=false` 去掉圆点、`resp=0.5`、`damp=0.62`、`s0=0.6` |
| `fx.caps(el, 文字, t0, o)` | 全大写、字距拉开的小标签 | `anim="wipe"`(从左擦出)/`"rise"`/`"fade"`、`track=0.32`(em)、`color`(默认 --c-mute)、`d=0.6` |

```js
fx.caps(hz.put(n, 0, -190, { cls: "cap" }), "github stars", 4.7, { color: "var(--c-warn)" });
fx.odo(hz.put(n, 0, -30, { cls: "num hz-shadow" }), 128640, 4.75, { d: 1.7, suffix: "+" });
const s = hz.put(n, 0, 150, { cls: "mid" }); fx.rise(s, "全部来自真实数据", 5.1, { gap: 0.04, grad: false });
fx.hl(s, 5.9, { color: "var(--c-warn)" });
fx.type(hz.put(n, -330, 0, { cls: "h2" }), "提示词写不好", 2.7, { delAt: 3.9, next: "交给 Claude" });
fx.pill(hz.put(n, 0, 175, { cls: "pl" }), "hz.canvas", 1.45);
fx.caret(hz.put(n, 0, 0, { cls: "h2" }), "讲过的退到身后", 7.35, { grad: true });
```

## 可用的类
`hz-grad` 奶白→暗的渐变字(老引擎大字质感)· `hz-shadow` 柔和投影 · `hz-at` 以 left/top 为中心定位 · `hz-pill` `hz-caps` 可单独当静态样式用。
大字字重按老规矩:越大越轻(≥200px 用 500,否则 500–600),不要外发光。

## 和 hz_ui3d.js(B)对接
- `hz.dive / hz.settle` 传 `cam:true` 时会调用 `hz.camTo(card, 起飞时刻, camOpts)`:签名一致,第一个参数是元素,第二个是**起飞时刻**(到位时刻 = 起飞 + `d`)。`camOpts` 就是上面的 camTo 选项(`d`、`fill`、`t1`、`rx/ry` 等)。
- 卡片在 dive 中会做 3D 变换,所以默认 `freeze:true`:在起飞那一刻量一次卡片矩形,之后固定,镜头不会跟着卡片抖动。要镜头追着卡片走,就传 `camOpts:{freeze:false}`。
- 画布的层级只靠 DOM 顺序和变换,**不用 z-index**。B 在 dive 期间把卡片和祖先的 z-index 临时抬到 1000 不会冲突。唯一用到 z-index 的地方是荧光笔笔触,它在文字自己的隔离层里,值为 -1。
