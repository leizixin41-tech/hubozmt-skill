"""工具公用:路径、本期文件夹、brief、引擎加载。"""
import os, sys, json, subprocess, importlib.util

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.path.join(SKILL, "engine")
LIB = os.path.join(SKILL, "library")
FONTLIB = os.path.join(LIB, "字体库")
ASSETLIB = os.path.join(LIB, "素材库")
STYLES = os.path.join(SKILL, "styles")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
for p in (ENGINE, FONTLIB, ASSETLIB):
    if p not in sys.path: sys.path.insert(0, p)

def ep_path(ep):
    """本期文件夹:可传绝对路径,或 episodes/ 下的名字。"""
    if os.path.isdir(ep): return os.path.abspath(ep)
    p = os.path.join(SKILL, "episodes", ep)
    if os.path.isdir(p): return p
    raise SystemExit(f"找不到本期文件夹: {ep}")

def brief(ep):
    """读 brief.json(机器可读的本期参数),缺省值见下。"""
    p = os.path.join(ep, "brief.json"); b = {}
    if os.path.exists(p): b = json.load(open(p, encoding="utf-8"))
    b.setdefault("size", "1920x1080"); b.setdefault("fps", 60); b.setdefault("style", "compositor-v1")
    return b

def run(cmd, **k):
    r = subprocess.run(cmd, capture_output=True, text=True, **k)
    if r.returncode != 0: raise SystemExit(f"命令失败: {' '.join(map(str, cmd))[:300]}\n{r.stderr[-1500:]}")
    return r.stdout

def probe(path):
    out = run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height,r_frame_rate,avg_frame_rate:format=duration", "-of", "json", path])
    return json.loads(out)

def voice_file(ep):
    """合成用的人声:剪过气口的优先。"""
    for n in ("voice_cut.wav", "voice.wav"):
        p = os.path.join(ep, "work", n)
        if os.path.exists(p): return p
    raise SystemExit("没有人声文件,先运行 hz ingest")

def setup_engine_env(ep, preview=False):
    b = brief(ep)
    os.environ["HZ_SIZE"] = b["size"]
    os.environ["HZ_ASSETS"] = os.path.join(ep, "assets")
    os.environ["CI_FPS"] = str(30 if preview else int(b["fps"]))
    os.environ["CI_SS"] = "1.0" if preview else os.environ.get("CI_SS", "1.25")
    os.environ["HZ_EPISODE"] = ep
    return b

def load_scenes(ep):
    """把本期 03_scenes.py 作为模块加载(引擎目录已在 sys.path)。"""
    p = os.path.join(ep, "03_scenes.py")
    if not os.path.exists(p): raise SystemExit("缺少 03_scenes.py")
    spec = importlib.util.spec_from_file_location("hz_scenes", p); m = importlib.util.module_from_spec(spec)
    sys.modules["hz_scenes"] = m; spec.loader.exec_module(m)
    for k in ("scene_nodes", "DUR", "BLOBS"):
        if not hasattr(m, k): raise SystemExit(f"03_scenes.py 缺少 {k}(见 engine/API.md 的脚本模板)")
    return m
