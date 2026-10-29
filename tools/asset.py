"""素材登记与清单(规则见 library/素材库/调用规范.md)。

用法:
  hz asset find --tags 标签1,标签2 [--kind 图片] [--all]     先查库,能复用就复用(--all 含「待确认」)
  hz asset use <本期> <素材id>                               把库里的素材拷进本期 assets/ 并记一笔
  hz asset add <本期> <文件> --type 图片|界面与截图|图标与标志|抠图|AI生成 --tags a,b,c
               --source 网址 --source-type 官网|推特|YouTube|网页|自制 --license "授权说明" --commercial 是|否|待确认
               [--note 备注]
        登记新素材:拷进素材库,同时放进本期 assets/(若不在)并记一笔。
  hz asset report <本期>                                     生成 out/素材清单.md(交付时附上)
"""
import os, sys, json, shutil, argparse, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *
from assetlib import add, find, path as apath, _load

def used_path(ep): return os.path.join(ep, "work", "assets_used.json")
def note_use(ep, rec):
    os.makedirs(os.path.join(ep, "work"), exist_ok=True); p = used_path(ep)
    L = json.load(open(p)) if os.path.exists(p) else []
    if not any(x.get("id") == rec.get("id") and x.get("file") == rec.get("file") for x in L): L.append(rec)
    json.dump(L, open(p, "w"), ensure_ascii=False, indent=1)

cmd = sys.argv[1] if len(sys.argv) > 1 else ""
if cmd == "find":
    ap = argparse.ArgumentParser(); ap.add_argument("cmd"); ap.add_argument("--tags", default=""); ap.add_argument("--kind"); ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    for it in find(tags=[t for t in a.tags.split(",") if t] or None, kind=a.kind, commercial_ok=(False if a.all else True)):
        print(f"{it['id']}  [{it['可商用']}]  {it['文件']}  标签={','.join(it['标签'])}")
elif cmd == "use":
    ep = ep_path(sys.argv[2]); aid = sys.argv[3]; src = apath(aid); it = next(x for x in _load()["素材"] if x["id"] == aid)
    os.makedirs(os.path.join(ep, "assets"), exist_ok=True); dst = os.path.join(ep, "assets", os.path.basename(src))
    if not os.path.exists(dst): shutil.copy2(src, dst)
    note_use(ep, dict(id=aid, file=os.path.relpath(dst, ep), source=it["来源"], license=it["授权"], commercial=it["可商用"]))
    print(dst)
elif cmd == "add":
    ap = argparse.ArgumentParser(); ap.add_argument("cmd"); ap.add_argument("ep"); ap.add_argument("file")
    for k in ("type", "tags", "source", "source_type", "license", "commercial"): ap.add_argument("--" + k.replace("_", "-"), required=True)
    ap.add_argument("--note", default="")
    a = ap.parse_args(); ep = ep_path(a.ep); f = os.path.abspath(a.file)
    meta = f[:-4] + ".json"
    note = a.note + ((" 截图信息:" + open(meta).read().replace("\n", " ")) if os.path.exists(meta) else "")
    name = f"{os.path.basename(ep)}_{os.path.basename(f)}"
    try:
        it = add(f, a.type, [t for t in a.tags.split(",") if t], a.source, a.source_type, a.license, a.commercial, 用途=os.path.basename(ep), 备注=note.strip(), 新文件名=name)
    except FileExistsError:
        it = next(x for x in _load()["素材"] if x["文件"].endswith(name))
    os.makedirs(os.path.join(ep, "assets"), exist_ok=True); dst = os.path.join(ep, "assets", os.path.basename(f))
    if os.path.abspath(dst) != f and not os.path.exists(dst): shutil.copy2(f, dst)
    note_use(ep, dict(id=it["id"], file=os.path.relpath(dst, ep), source=a.source, license=a.license, commercial=a.commercial))
    print(json.dumps(dict(id=it["id"], file=dst), ensure_ascii=False))
elif cmd == "report":
    ep = ep_path(sys.argv[2]); L = json.load(open(used_path(ep))) if os.path.exists(used_path(ep)) else []
    gp = os.path.join(ep, "work", "gen_log.json"); G = json.load(open(gp)) if os.path.exists(gp) else []
    out = [f"# 素材清单 · {os.path.basename(ep)}", "", f"生成时间 {time.strftime('%Y-%m-%d %H:%M')}", "",
           "| 素材 | 来源 | 授权 | 可商用 |", "|---|---|---|---|"]
    for x in L: out.append(f"| {x['file']} | {x['source']} | {x['license']} | {x['commercial']} |")
    for g in G: out.append(f"| {g['file']} | libTV 生成(模型 {g['model']},任务 {g.get('task')}) | libTV 会员生成,商用条款待核实 | 待确认 |")
    pend = [x for x in L if x["commercial"] != "是"] + G
    out += ["", f"**发布前需要确认授权的素材:{len(pend)} 个**" if pend else "全部素材可商用。"]
    os.makedirs(os.path.join(ep, "out"), exist_ok=True); p = os.path.join(ep, "out", "素材清单.md"); open(p, "w", encoding="utf-8").write("\n".join(out) + "\n"); print(p)
else:
    print(__doc__)
