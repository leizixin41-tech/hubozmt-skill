"""素材库调用接口。  from assetlib import find, path, add
find(tags=["花","橙色"], kind="图片", commercial_ok=True)  → 素材条目列表
path("img_0002")                                          → 绝对路径
add(src_file, 类型="图片", 标签=[...], 来源="...", 来源类型="官网", 授权="...", 可商用="是/否/待确认", ...)
规则见 调用规范.md。"""
import os, json, shutil, datetime
HERE = os.path.dirname(os.path.abspath(__file__)); IDX = os.path.join(HERE, "索引.json")
def _load(): return json.load(open(IDX, encoding="utf-8"))
def _save(d): json.dump(d, open(IDX, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
def find(tags=None, kind=None, commercial_ok=True, text=None):
    """commercial_ok=True 时只返回『可商用=是』;=False 时包含待确认(仅限草稿);None 不过滤。"""
    out = []
    for it in _load()["素材"]:
        if kind and it["类型"] != kind: continue
        if commercial_ok is True and it["可商用"] != "是": continue
        if commercial_ok is False and it["可商用"] == "否": continue
        if tags and not all(any(t in x for x in it["标签"]) for t in tags): continue
        if text and text not in json.dumps(it, ensure_ascii=False): continue
        out.append(it)
    return out
def path(id_):
    for it in _load()["素材"]:
        if it["id"] == id_: return os.path.join(HERE, it["文件"])
    raise KeyError(id_)
def add(src, 类型, 标签, 来源, 来源类型, 授权, 可商用, 用途="", 备注="", 提示词=None, 模型=None, 种子=None, 衍生自=None, 子目录=None, 新文件名=None):
    d = _load(); n = len(d["素材"]) + 1; pref = {"图片": "img", "界面与截图": "ui", "图标与标志": "icon", "抠图": "cut", "视频片段": "vid", "AI生成": "ai"}.get(类型, "x")
    sub = 子目录 or 类型; os.makedirs(os.path.join(HERE, sub), exist_ok=True)
    name = 新文件名 or os.path.basename(src); dst = os.path.join(HERE, sub, name)
    if os.path.exists(dst): raise FileExistsError("不覆盖已有文件:" + dst)
    shutil.copy2(src, dst)
    try:
        from PIL import Image; im = Image.open(dst); w, h = im.size
    except Exception: w = h = None
    it = dict(id=f"{pref}_{n:04d}", 文件=os.path.join(sub, name), 类型=类型, 标签=标签, 来源=来源, 来源类型=来源类型, 授权=授权, 可商用=可商用, 尺寸=[w, h], 比例=(round(w / h, 3) if w else None), 用途=用途, 备注=备注, 加入日期=datetime.date.today().isoformat())
    if 提示词: it["AI"] = dict(提示词=提示词, 模型=模型, 种子=种子)
    if 衍生自: it["衍生自"] = 衍生自
    d["素材"].append(it); _save(d); return it
