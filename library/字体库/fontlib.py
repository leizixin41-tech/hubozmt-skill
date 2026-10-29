"""字体库调用接口。只能通过角色(role)取字体,不允许在场景里直接写字体文件路径。
用法:  from fontlib import face
       f = face("serif", 120, 700)           # 返回 PIL ImageFont(自动设置可变字重)
       f = face("punch", 140, ch="太")        # 按字符自动选 中文/拉丁 字体
规范见 使用规范.md,授权见 字体清单.json。"""
import os
from PIL import ImageFont
HERE = os.path.dirname(os.path.abspath(__file__))
P = lambda *a: os.path.join(HERE, *a)

def _static(d, name): return P(d, name)
ROLES = {
  # 角色:   (中文字体, 拉丁字体)  每项 = (文件, 可变轴类型 或 None 或 {字重: 文件})
  "sans":  ({300: P("NotoSansSC", "NotoSansSC-Light.otf"), 400: P("NotoSansSC", "NotoSansSC-Regular.otf"), 500: P("NotoSansSC", "NotoSansSC-Medium.otf"), 700: P("NotoSansSC", "NotoSansSC-Bold.otf")},
            {300: P("Inter", "Inter-Light.otf"), 400: P("Inter", "Inter-Regular.otf"), 500: P("Inter", "Inter-Medium.otf"), 600: P("Inter", "Inter-SemiBold.otf"), 700: P("Inter", "Inter-Bold.otf"), 800: P("Inter", "Inter-ExtraBold.otf"), 900: P("Inter", "Inter-Black.otf")}),
  "serif": (("var", P("NotoSerifSC", "NotoSerifSC[wght].ttf"), ("wght",)),
            ("var", P("Fraunces", "Fraunces[SOFT,WONK,opsz,wght].ttf"), ("opsz", "wght", "SOFT", "WONK"))),
  "serif2": (("var", P("NotoSerifSC", "NotoSerifSC[wght].ttf"), ("wght",)),
             {400: P("InstrumentSerif", "InstrumentSerif-Regular.ttf")}),
  "hand":  ({400: P("LXGW-WenKai", "LXGWWenKai-Regular.ttf"), 500: P("LXGW-WenKai", "LXGWWenKai-Medium.ttf")},
            {400: P("LXGW-WenKai", "LXGWWenKai-Regular.ttf"), 500: P("LXGW-WenKai", "LXGWWenKai-Medium.ttf")}),
  "punch": ({400: P("ZCOOL-QingKe-HuangYou", "ZCOOLQingKeHuangYou-Regular.ttf")}, {400: P("ZCOOL-QingKe-HuangYou", "ZCOOLQingKeHuangYou-Regular.ttf")}),
  "oblique": ({400: P("SmileySans", "SmileySans-Oblique.ttf")}, {400: P("SmileySans", "SmileySans-Oblique.ttf")}),
  "grot":  ({300: P("NotoSansSC", "NotoSansSC-Light.otf"), 400: P("NotoSansSC", "NotoSansSC-Regular.otf"), 500: P("NotoSansSC", "NotoSansSC-Medium.otf"), 700: P("NotoSansSC", "NotoSansSC-Bold.otf")},
            ("var", P("SpaceGrotesk", "SpaceGrotesk[wght].ttf"), ("wght",))),
  "bric":  ({300: P("NotoSansSC", "NotoSansSC-Light.otf"), 400: P("NotoSansSC", "NotoSansSC-Regular.otf"), 500: P("NotoSansSC", "NotoSansSC-Medium.otf"), 700: P("NotoSansSC", "NotoSansSC-Bold.otf")},
            ("var", P("BricolageGrotesque", "BricolageGrotesque[opsz,wdth,wght].ttf"), ("opsz", "wdth", "wght"))),
  "mono":  ({400: P("NotoSansSC", "NotoSansSC-Regular.otf"), 500: P("NotoSansSC", "NotoSansSC-Medium.otf")},
            ("var", P("JetBrainsMono", "JetBrainsMono[wght].ttf"), ("wght",))),
}
_cache = {}
def is_cjk(ch): return ord(ch) >= 0x2E80

def _axes_values(kind_axes, size, weight):
    out = []
    for a in kind_axes:
        if a == "wght": out.append(weight)
        elif a == "opsz": out.append(max(9, min(144, size)))
        elif a == "wdth": out.append(100)
        elif a == "SOFT": out.append(0)
        elif a == "WONK": out.append(0)
        else: out.append(0)
    return out

def _open(spec, size, weight):
    size = max(6, int(round(size)))
    if isinstance(spec, dict):
        w = min(spec, key=lambda k: abs(k - weight)); path = spec[w]; key = (path, size)
        if key not in _cache: _cache[key] = ImageFont.truetype(path, size)
        return _cache[key]
    _, path, axes = spec; vals = _axes_values(axes, size, weight); key = (path, size, tuple(vals))
    if key not in _cache:
        f = ImageFont.truetype(path, size)
        info = f.get_variation_axes(); mapped = []
        for ax, v in zip(info, [None] * len(info)):
            pass
        # 按字体自身的轴顺序取值(名称匹配)
        names = [a["name"].decode().lower() for a in info]; vv = []
        for a, nm in zip(info, names):
            want = {"weight": weight, "optical size": max(a["minimum"], min(a["maximum"], size)), "optical": max(a["minimum"], min(a["maximum"], size)), "width": 100, "softness": 0, "wonky": 0}
            val = next((v for k, v in want.items() if k in nm), a["default"]); vv.append(max(a["minimum"], min(a["maximum"], val)))
        f.set_variation_by_axes(vv); _cache[key] = f
    return _cache[key]

def face(role, size, weight=500, ch=None, cjk=None):
    """role:见 ROLES。ch 给出时自动选中文/拉丁;cjk=True/False 可强制。"""
    c, l = ROLES[role]
    use_cjk = cjk if cjk is not None else (is_cjk(ch) if ch else False)
    return _open(c if use_cjk else l, size, weight)

def has_glyphs(role, text):
    """检查该角色的字体是否包含 text 里全部字符(缺字会显示成方块)。返回缺字列表。"""
    miss = []
    for ch in text:
        if ch.isspace(): continue
        f = face(role, 40, 500, ch=ch)
        try:
            m = f.getmask(ch); bb = f.getbbox(ch)
            if bb is None or (bb[2] - bb[0]) <= 0: miss.append(ch)
        except Exception: miss.append(ch)
    return miss
