"""从 UI组件库(uiverse.io 开源库,MIT)取组件,打包成场景页可直接用的 JS。

用法:
  hz uiverse find <关键词|类别> [--feat 3D透视] [--n 30]     查组件(类别:Buttons Cards Checkboxes Forms Inputs loaders
                                                            Notifications Patterns Radio-buttons Toggle-switches Tooltips)
  hz uiverse use <本期> <编号> [<编号> ...]                 打包到 <本期>/assets/uiverse.js,并登记作者到 work/uiverse_credits.json

总览图在 library/UI组件库/总览图/<类别>_NN.jpg,图上红字 #编号 就是这里的编号。
场景页里:<script src="assets/uiverse.js"></script> 之后,用 hz.ui(编号, {zoom, bg}) 生成 iframe。
组件里的 :hover / :active 会被改写成 .hz-h / .hz-a 类,方便按时间触发(hz.state)。
"""
import json, os, re, sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from _common import ep_path, LIB  # noqa

LIBDIR = Path(LIB, "UI组件库")


def load():
    return json.load(open(LIBDIR / "index.json"))


def find(a):
    rows = load(); q = a[0].lower() if a and not a[0].startswith("--") else ""
    feat = a[a.index("--feat") + 1] if "--feat" in a else None
    n = int(a[a.index("--n") + 1]) if "--n" in a else 30
    hits = [r for r in rows if (q in r["cat"].lower() or any(q in t.lower() for t in r["tags"]) or q in r["file"].lower())
            and (not feat or feat in r["feat"]) and not r["tw"]]
    for r in hits[:n]:
        print(f"#{r['id']:<5} {r['cat']:<16} {r['file'].split('_')[0]:<22} {','.join(r['feat'])}")
    print(f"共 {len(hits)} 个(只列纯 CSS 的;Tailwind 写的需要联网加载,先不用)")


def use(a):
    ep = ep_path(a[0]); ids = [int(x.lstrip("#")) for x in a[1:]]
    rows = load(); out = {}; credits = []
    for i in ids:
        r = rows[i]
        src = (LIBDIR / "galaxy" / r["cat"] / r["file"]).read_text(errors="ignore")
        src = re.sub(r":hover\b", ".hz-h", src)
        src = re.sub(r":active\b", ".hz-a", src)
        author = r["file"].split("_")[0]
        out[i] = dict(html=src, author=author, cat=r["cat"])
        credits.append(dict(id=i, author=author, cat=r["cat"], file=r["file"], license="MIT", source="uiverse.io"))
    Path(ep, "assets").mkdir(exist_ok=True)
    Path(ep, "assets", "uiverse.js").write_text("window.UIVERSE=" + json.dumps(out, ensure_ascii=False) + ";")
    Path(ep, "work").mkdir(exist_ok=True)
    Path(ep, "work", "uiverse_credits.json").write_text(json.dumps(credits, ensure_ascii=False, indent=1))
    print(f"已打包 {len(ids)} 个组件 → assets/uiverse.js;作者:{', '.join(sorted({c['author'] for c in credits}))}")


if __name__ == "__main__":
    {"find": find, "use": use}[sys.argv[1]](sys.argv[2:])
