"""网页渲染器:把一个「按时间可定格」的 HTML 场景页逐帧截图成视频。

用法: hz web_render <本期> [preview|final|still t1 t2 ...] [--page 03_scene.html] [--workers 6]

规范 v2 的期(brief.json 里 "spec": 2):preview/final 前先过段表门禁(hz plan),且 out/check.json 必须是改完之后跑的全片检查并且通过。
场景页约定(见 engine/WEB.md):页面定义 window.HZ = {dur: 秒, seek: async t => {...}}。
seek(t) 必须把画面「定格」到 t 秒(纯函数,不能依赖真实时间)。渲染器会暂停页面里所有 CSS 动画/过渡,
再由 seek 统一设置 currentTime,所以 CSS @keyframes 也能用 —— 见 WEB.md 的 hz.css 工具。
"""
import os, sys, subprocess, time, json, multiprocessing as mp
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from _common import ep_path, brief, voice_file  # noqa
from _cdp import Browser

SEEK = "(async()=>{await window.HZ.seek(%f);await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));return 1})()"


def open_page(ep, page, w, h):
    b = Browser(w, h, proxy=os.environ.get("HZ_PROXY", "127.0.0.1:7897"))
    b.goto(Path(ep, page).resolve().as_uri(),
           "window.HZ && window.HZ.ready === true && document.fonts.status==='loaded'", timeout=60)
    return b


def worker(args):
    ep, page, w, h, frames, fps, outdir, q = args
    b = open_page(ep, page, w, h)
    try:
        for fi in frames:
            b.js(SEEK % (fi / fps))
            Path(outdir, f"{fi:06d}.jpg").write_bytes(b.shot("jpeg", q))
    finally:
        b.close()
    return len(frames)


def main():
    a = sys.argv[1:]
    ep = ep_path(a[0]); mode = a[1] if len(a) > 1 else "preview"
    page = "03_scene.html"; workers = 6
    if "--page" in a: page = a[a.index("--page") + 1]
    if "--workers" in a: workers = int(a[a.index("--workers") + 1])
    bf = brief(ep); w, h = map(int, bf["size"].split("x"))
    out = Path(ep, "out"); out.mkdir(exist_ok=True)
    if mode != "still" and int(bf.get("spec", 1)) >= 2:   # 规范 v2:段表门禁 + 最近一次全片检查通过,才许渲染
        from plan import gate
        P, _ = gate(ep)
        if P:
            print("❌ 段表门禁没过,不渲染(hz plan 看详情):"); [print("  -", x) for x in P[:20]]; sys.exit(1)
        cj = out / "check.json"; src = [Path(ep, n) for n in (page, "02_段表.json") if Path(ep, n).exists()]
        ck = json.load(open(cj)) if cj.exists() else {}
        if not ck.get("ok") or not ck.get("full", True) or any(p.stat().st_mtime > cj.stat().st_mtime for p in src):
            print("❌ 还没有通过「改完之后的全片检查」,不渲染。先跑:bin/hz check " + Path(ep).name); sys.exit(1)

    if mode == "still":
        ts = [float(x) for x in a[2:] if not x.startswith("--") and x.replace(".", "", 1).isdigit()]
        b = open_page(ep, page, w, h)
        for t in ts:
            b.js(SEEK % t)
            p = out / f"still_{t:06.2f}.png"; p.write_bytes(b.shot("png")); print(p)
        b.close(); return

    fps = int(bf.get("fps", 30))
    b = open_page(ep, page, w, h); dur = float(b.js("window.HZ.dur")); b.close()
    n = int(round(dur * fps))
    fdir = Path(ep, "work", "frames");
    if fdir.exists():
        for f in fdir.glob("*.jpg"): f.unlink()
    fdir.mkdir(parents=True, exist_ok=True)
    q = 90 if mode == "preview" else 97
    chunks = [list(range(i, n, workers)) for i in range(workers)]
    t0 = time.time()
    with mp.Pool(workers) as pool:
        done = sum(pool.map(worker, [(ep, page, w, h, c, fps, str(fdir), q) for c in chunks]))
    print(f"截帧 {done} 帧,用时 {time.time()-t0:.0f} 秒")

    name = "preview.mp4" if mode == "preview" else f"{Path(ep).name}.mp4"
    mix = out / "mix.wav"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", str(fdir / "%06d.jpg")]
    if mix.exists():
        cmd += ["-i", str(mix), "-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium",
            "-crf", "20" if mode == "preview" else "16", "-movflags", "+faststart", str(out / name)]
    subprocess.run(cmd, check=True)
    if mode != "preview":
        for f in fdir.glob("*.jpg"): f.unlink()
    print(out / name)


if __name__ == "__main__":
    main()
