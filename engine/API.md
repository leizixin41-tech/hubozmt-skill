# 引擎速查(合成师必读)

纯 Python(numpy / OpenCV / Pillow)逐帧渲染。**整片在一张无限画布上**,每段内容是一个**节点(node)**,镜头按时间在节点之间飞(缩放+平移),旧节点自动**虚化、压暗、轻微后退**,形成层级。
场景脚本只需 `from kit import *`,就能用到下面所有东西。

## 坐标与时间
- **世界坐标**:单位是「镜头缩放 1.0 时的屏幕像素」。节点内元素用**相对节点中心**的坐标 `(x, y)`,y 向下为正。
- 当前画面尺寸:`W`、`H`(由 brief.json 决定,**不要写死**)。缩放为 `zoom` 的节点,可见范围约为 `±W/2/zoom × ±H/2/zoom`,四周留约 40 像素安全边距。
- **时间都是成片里的绝对秒数**(和口播逐句稿一致;剪过气口就用剪后的时间)。
- 节点 `t_in` = 镜头**到位**的时刻;镜头在 `t_in - flight*pre` 起飞,飞行 `flight` 秒。
- 节点排布:默认由 `finish()` 自动排开(横屏沿 x、竖屏沿 y,轻微错落)。想自己摆就用 `node(..., pos=(x, y), fixed=True)`。

## 脚本模板(复制后改)
```python
from kit import *

# 本模板按 16:9 写;别的比例要按 W、H 重新定字号和位置(hz check 会报出画)
DUR = 29.3                                  # 成片总时长 = 人声时长 + 0.5~1 秒收尾

# ===== 段 1 · 0.00–2.40 · 开场钩子
n0 = node("hook", 0.0, zoom=1.0, flight=0.01, drift=(0.012, 6, 0))      # 第一个节点 flight 极小
tag2(n0, "prompt engineering", 24, STONE, 0, -330, 0.3)
big(n0, "不会写提示词", 200, 700, 0, -40, 0.15, 0.07, lambda: A_rise(0.9, 70, blur=16))
deco(n0, flat_card(600, 10, VIOLET, 5, shadow=None, border=0), 0, 238, 1.55, A_wipe(0.6, E_OUT, 0.1))
blob(n0, 0, 0, VIOLET, 900, 0.10)                                      # 背景彩色光斑(可选)

# ===== 段 2 · 2.40–3.60 · 项目亮相
n1 = node("name", 2.2, zoom=1.05, flight=0.8, ease=E_EXPO, pre=0.4, drift=(0.012, 0, -4))
card_el(n1, icon_sprite(240, "logo.png"), 0, -200, 2.25, A_pop(0.7, 0.5, 1.6, blur=10), z=0.5)
big(n1, "Prompt Optimizer", 140, 800, 0, 40, 2.35, 0.03, lambda: A_rise(0.5, 60, blur=12), role=GROT)

BLOBS = finish()                            # 必须:排布节点 + 背景光斑
scene_nodes = nodes                         # 必须

SFX = [(0.15, "thump", 0.5), (2.25, "pop", 0.3, {"f0": 520, "f1": 1000})]   # 音效(见下)
```

## 节点
`node(name, t_in, pos=(0,0), zoom=1.0, fixed=False, flight=0.7, ease=E_EXPO, pre=0.75, drift=(dzoom/秒, dx/秒, dy/秒))`
- 节点内推镜:`n.key(t0, t1, off=(dx, dy), zoom=1.1)`,在 t0→t1 把镜头移到相对节点中心的 off 并放大(注意别把字推出画面)。
- 背景风格(可选,按节点切换,镜头飞行时平滑过渡):`n.style = dict(base_c=(r,g,b), base_e=(r,g,b), gobo=0.04, dots=0.07, vign=0.38, grain=0.016, blobs=[(dx,dy,颜色,半径,强度)])`。不设就是默认的深色电影感背景。
- 缓动:`E_OUT` `E_EXPO`(快起慢停)`E_INOUT`(两头慢)`E_SOFT` `E_IN` `E_LIN`,`e_back(x, c)`(回弹)。

## 放元素(都会自动登记版面,供 `hz check` 查遮挡)
| 函数 | 作用 |
|---|---|
| `big(n, 文字, 字号, 字重, cx, cy, t0, 逐字间隔, anim工厂, role=SANS, color=None, grad=None, tracking=0)` | 逐字出现的大字;`anim工厂` 是 `lambda: A_rise(...)` 这种;返回逐字元素列表(可再挂 `e.custom`) |
| `line(n, 文字, 字号, 字重, 颜色, cx, cy, t0, anim, role=SANS, shadow=None)` | 整行文字 |
| `tag2(n, 文字, 字号, 颜色, cx, cy, t0, tracking=0.3)` | 英文大写小标签(字距拉开) |
| `pill_el(n, 文字, cx, cy, t0, size=30, fg=CREAM, bg=None, dot=None)` | 胶囊标签(bg 填色 / dot 左侧圆点) |
| `card_el(n, 精灵, x, y, t0, anim, z=0, rot=0, custom=None)` | 放卡片/图片/图标 |
| `shot(文件名, crop=(x0,y0,x1,y1), w=宽, radius=14, chrome="mac"/None, title=None)` | 读 assets/ 里的图做成卡片精灵(可裁切、可加窗口标题栏) |
| `icon_sprite(宽, 文件名)` | 透明底图标 → 带投影的精灵 |
| `deco(n, 精灵, x, y, t0, anim)` | 装饰(角标、线条、光点):不参与遮挡检查 |
| `video_el(n, 视频, x, y, w, h=None, t0, src_t0=None, radius=18, focus=(0.5,0.5), anim=None, t1=None)` | **真人/视频画面**,与成片时间同步播放;给 h 时按 focus 居中裁切铺满;整屏用 `w=W/zoom, h=H/zoom, radius=0` |
| `El(精灵, x, y, t0, anim, z=0, scale=1, rot=0, custom=None, t1=None, fade_out=0.3)` + `n.add(el)` | 底层放法(不登记版面;要查遮挡就自己 `reg(n, "text"/"card", x, y, w, h)`) |

精灵(Sprite)来源:`text_sprite(文字, 字号, 字重, 颜色, grad=, tracking=, shadow=(dx,dy,blur,alpha), role=)`、`giant(文字, 字号, 字重, color=)`(渐变大字)、`flat_card(w, h, 颜色, radius, shadow=, gradient=(c0,c1))`、`pill(...)`、`bracket(70, 6, 颜色, "tl"/"tr"/"bl"/"br")`、`ring_sprite(r, 粗细, 颜色)`、`sparkle(尺寸, 颜色)`、`star5(尺寸, 颜色)`、`arrow_sprite(长, 颜色)`、`hl(w, h, 颜色)`(描边框)、`vbar(h, 颜色)`、`cursor_sprite()`、`keycap("Enter")`、`file_icon(".zip")`、`raster_sprite(画图函数, w, h)`(用 PIL 自己画)。

## 动画(anim:输入「元素出现后的秒数」,输出状态)
`A_rise(d, dy, blur, ease, dx, s0)` 上浮淡入 · `A_pop(d, s0, c, blur)` 弹出 · `A_drop(d, dy, rot0, s0)` 从上落下 · `A_wipe(d, ease, soft)` 从左到右擦出 · `A_fade(d)` 淡入 · `A_ring(d, s0, s1)` 光圈扩散 · `A_grow_y(d)` 竖向长出 · `slide_dim(dx, t0, t_dim)` 侧滑进入并在 t_dim 变暗。
- 状态字段:`a`(透明度)`dx dy`(位移)`s`(缩放)`sy`(竖向缩放)`rot`(角度)`blur`(模糊)`reveal`(擦出进度)。
- `custom=lambda t: dict(...)`:按**绝对时间** t 叠加/覆盖状态(做漂浮、抖动、后续放大等)。
- `t1=秒`:到点淡出消失。

## 现成动效组件(按内容挑,也可以组合或自己写新的)
| 组件 | 适合表达 |
|---|---|
| `type_delete(n, 文字, cx, cy, t0, 打字间隔, 开始删除时刻, 删除间隔, 字号, 字重, 颜色, 光标消失时刻)` | 打了又删:犹豫、不会写、改主意 |
| `typed(n, 文字, 左端x, cy, t0, 间隔, size, w, color)` | 逐字打出 + 光标 |
| `strip_card(n, 文件名, crop, w, cx, cy, t0, 行间隔, title=None)` | 截图里的文字**一行一行**出现:结构、清单、生成过程 |
| `odometer(n, 数值, x, y, 字号, t0, t1)` | 数字滚动:star 数、用户量、价格 |
| `timer_el(n, x, y, 半径, t0, 时长, 颜色)` | 计时圈:几秒钟、很快 |
| `check_el(n, x, y, 尺寸, t0, 时长, 颜色)` | 画勾:正确、完成 |
| `hl(w, h, 颜色)` + `A_pop` / `ring_sprite` + `A_ring` | 圈出截图里的重点 |
| `slide_dim` + `hl` | 对比:前后两栏滑入,一暗一亮 |
| 逐字元素挂 `e.custom` 做模糊/抖动 | 「模糊」「说不清」「紧张」等情绪字 |

## 自绘元素(做现成组件没有的效果)
```python
def paint(canvas, f, k, st):
    # canvas: 当前节点的画布(H×W×4,预乘 alpha,float32)
    # f(lx, ly) -> 画布像素坐标(lx, ly 是相对元素位置的局部坐标)
    # k: 局部 1 个单位 = 画布上 k 个像素(已含镜头缩放)
    # st["t"]: 绝对时间;st["a"]: 透明度
    X, Y = f(0, 0)
    draw_aa(canvas, lambda m: cv2.circle(m, (int(X*16), int(Y*16)), int(40*k*16), 255, max(1, int(4*k)), cv2.LINE_AA, 4), VIOLET, st["a"])
n.add(El(None, x, y, t0, A_fade(0.2), paint=paint)); reg(n, "text", x, y, 宽, 高)   # 需要查遮挡时登记
```
`draw_aa(canvas, 画掩码函数, 颜色, alpha, blur)`:在 uint8 掩码上用 OpenCV 画(坐标×16,shift=4 抗锯齿),再叠上颜色。

## 字体
`role=` 选字体库角色:`SANS`(思源黑体+Inter,默认)、`GROT`(Space Grotesk,英文/数字)、`MONO_`(等宽,网址/代码)、`"serif"`(思源宋体+Fraunces)、`"serif2"`、`"hand"`(霞鹜文楷)、`"punch"`(站酷庆科黄油体,1–4 字冲击词)、`"oblique"`(得意黑)、`"bric"`。缺字会直接报错,换角色即可。

## 颜色
`hexc("#RRGGBB")`;预设 `CREAM STONE DIMTX INK ORANGE ORANGE2 TEAL BLUE PINK GREEN RED VIOLET VIOLET2`。

## 音效(脚本末尾的 SFX 列表,`hz sfx` 读取)
`(时刻, 种类, 音量[, {参数, "pan": -1~1}])`;种类:`whoosh(dur,bright)` `thump(f0,dur,click)` `tick(f,dur,tone)` `keytap(depth)` `pop(f0,f1,dur)` `chime(f,dur)` `shimmer(dur,base)` `swish(dur)`。镜头飞行自动配呼啸(`AUTO_WHOOSH = False` 关闭)。音量参考:轻 0.2–0.3,中 0.4–0.6,重 0.8–1.0。

## 检查
`hz check <本期>` 用的是 `check_layout()`:同一节点内文字与文字/卡片重叠、超出画面、相邻节点压盖、每段最后一个元素出现后不足 0.6 秒镜头就离开 —— 都会报出来。
