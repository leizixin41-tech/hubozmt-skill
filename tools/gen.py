"""用 libTV 生成图片,下载到本期 assets/,并登记进素材库。

用法: hz gen <本期> <名字> "<提示词>" [--model "Lib Image 2.5 Pro"] [--ratio 16:9] [--quality high]
              [--ref 本地参考图.png] [--tags 标签1,标签2,标签3]
  名字:素材的短名(中文可),也是 libTV 画布上节点的名字;同名会自动加序号。
  --ref:图生图时的参考图(本地文件),会先上传到画布再连到生成节点。
  每期默认最多生成 20 张(brief.json 里 "gen_limit" 可改);超出时停止并提示,需要用户同意再加。
  模型列表:`libtv model search --type image`;某模型可调参数:`libtv model <modelKey>`。
产出: assets/ai_<名字>.png;work/gen_log.json 追加一条(提示词/模型/任务号/画布)。
"""
import os, sys, json, time, argparse, subprocess, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *

LIBTV = os.path.expanduser("~/.libtv/libtv")
CFG = json.load(open(os.path.join(SKILL, "config.json")))

def tv(args, cwd, retries=3, want_json=True):
    for k in range(retries):
        r = subprocess.run([LIBTV] + args, cwd=cwd, capture_output=True, text=True)
        if r.returncode == 0:
            return json.loads(r.stdout) if want_json and r.stdout.strip().startswith("{") else r.stdout
        err = r.stderr.strip()[-600:]
        if k < retries - 1 and any(x in err for x in ("503", "502", "504", "timeout", "ECONN")):
            print(f"libTV 暂时不可用,{15 * (k + 1)} 秒后重试…", flush=True); time.sleep(15 * (k + 1)); continue
        raise SystemExit(f"libtv {' '.join(args[:3])} 失败:\n{err}")

ap = argparse.ArgumentParser(); ap.add_argument("ep"); ap.add_argument("name"); ap.add_argument("prompt")
ap.add_argument("--model", default="Lib Image 2.5 Pro"); ap.add_argument("--ratio", default="16:9"); ap.add_argument("--quality", default="high")
ap.add_argument("--ref"); ap.add_argument("--tags", default="")
a = ap.parse_args()
EP = ep_path(a.ep); B = brief(EP); os.makedirs(os.path.join(EP, "assets"), exist_ok=True); os.makedirs(os.path.join(EP, "work"), exist_ok=True)
logp = os.path.join(EP, "work", "gen_log.json"); log = json.load(open(logp)) if os.path.exists(logp) else []
limit = int(B.get("gen_limit", CFG.get("gen_limit_default", 20)))
if len(log) >= limit: raise SystemExit(f"本期已生成 {len(log)} 张,达到上限 {limit}。请先问用户是否追加(改 brief.json 的 gen_limit)。")

# 本期画布:没有就在 hubozmt-skill 工作区里新建一张,并绑定到本期文件夹
state = os.path.join(EP, ".libtv", "project.json")
if not (os.path.exists(state) and json.load(open(state)).get("projectUuid")):
    tv(["workspace", "use", str(CFG["libtv_workspace_id"])], EP)
    tv(["project", "create", os.path.basename(EP)], EP)
    lst = tv(["project", "list"], EP)["projectMetaList"]
    uuid = next(p["uuid"] for p in lst if p["name"] == os.path.basename(EP))
    tv(["project", "use", uuid], EP)
canvas = json.load(open(state))["projectUuid"]

used = {e["name"] for e in log}; name = a.name; i = 2
while name in used: name = f"{a.name}_{i}"; i += 1
args = ["node", "create", name, "-t", "image", "--prompt", a.prompt, "-s", f"model={a.model}", "-s", f"ratio={a.ratio}", "-s", f"quality={a.quality}"]
if a.ref:
    tv(["upload", name + "_参考", "-t", "image", "--resource", os.path.abspath(a.ref)], EP); args += ["--left", name + "_参考", "-s", "modeType=image2image"]   # 有参考图必须切图生图模式
tv(args, EP)
print(f"生成中:{name}(约 20–60 秒)…", flush=True)
res = tv(["node", name, "--run"], EP)
dl = None
for wm in ("false", "true"):
    r = subprocess.run([LIBTV, "download", "-n", name, "--watermark", wm, "-o", os.path.join(EP, "work")], cwd=EP, capture_output=True, text=True)
    if r.returncode == 0 and r.stdout.strip(): dl = r.stdout.strip().splitlines()[-1]; watermark = wm == "true"; break
if not dl: raise SystemExit("生成成功但下载失败:" + r.stderr[-400:])
ext = os.path.splitext(dl)[1] or ".png"; dst = os.path.join(EP, "assets", f"ai_{name}{ext}"); shutil.move(dl, dst)

entry = dict(name=name, file=os.path.relpath(dst, EP), prompt=a.prompt, model=a.model, ratio=a.ratio, quality=a.quality, ref=a.ref,
             task=res.get("taskId"), node=res.get("nodeKey"), canvas=canvas, watermark=watermark, time=time.strftime("%Y-%m-%d %H:%M"))
log.append(entry); json.dump(log, open(logp, "w"), ensure_ascii=False, indent=1)
# 登记素材库
from assetlib import add
tags = [t for t in a.tags.split(",") if t] + ["AI生成", "libTV"]
try:
    it = add(dst, "AI生成", tags, f"libTV 画布 {canvas} 节点 {res.get('nodeKey')}", "AI生成", "libTV 会员生成(商用条款待核实)", "待确认",
             用途=os.path.basename(EP), 提示词=a.prompt, 模型=a.model, 种子=res.get("taskId"), 新文件名=f"ai_{os.path.basename(EP)}_{name}{ext}")
    entry["asset_id"] = it["id"]; json.dump(log, open(logp, "w"), ensure_ascii=False, indent=1)
except FileExistsError: pass
print(json.dumps(entry, ensure_ascii=False))
