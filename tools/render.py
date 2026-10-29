"""按本期 03_scenes.py 渲染。尺寸/帧率来自 brief.json。

用法:
  hz render <本期> still 3.0 5.2 ...        单帧 PNG → out/still_<秒>.png(成片档质量)
  hz render <本期> board <名字> 1.0 2.5 ...  多帧拼图 → out/<名字>.jpg(快速看构图)
  hz render <本期> preview                   预览档:30 帧、低超采样 → out/preview.mp4(带声音,如果已有 out/mix.wav)
  hz render <本期> final                     成片档:brief 里的帧率 → out/<本期名>.mp4(带声音)
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *

if __name__ == "__main__":
    EP = ep_path(sys.argv[1]); MODE = sys.argv[2]
    os.environ["HZ_EPISODE"] = EP; os.environ["HZ_MODE"] = MODE
EP = os.environ["HZ_EPISODE"]; MODE = os.environ["HZ_MODE"]
B = setup_engine_env(EP, preview=(MODE in ("preview", "board")))
from ci_frame import *                     # noqa: E402  (尺寸环境变量必须先设好)
SC_MOD = load_scenes(EP)
SC = Scene(SC_MOD.scene_nodes, SC_MOD.DUR, SC_MOD.BLOBS)
OUT = os.path.join(EP, "out"); os.makedirs(OUT, exist_ok=True)

def _chunk(args):
    a, b = args; return [render_frame(SC, i).tobytes() for i in range(a, b)]

def video(dst):
    import multiprocessing as mp, subprocess
    n1 = int(SC.duration * FPS); CH = 6
    chunks = [(i, min(i + CH, n1)) for i in range(0, n1, CH)]
    silent = dst[:-4] + "_silent.mp4"
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                           "-c:v", "libx264", "-crf", "17" if MODE == "final" else "23", "-preset", "medium" if MODE == "final" else "veryfast", "-pix_fmt", "yuv420p", silent], stdin=subprocess.PIPE)
    t_s = time.time(); workers = max(2, (os.cpu_count() or 4) - 1)
    with mp.Pool(workers) as pool:
        for k, res in enumerate(pool.imap(_chunk, chunks)):
            for b in res: ff.stdin.write(b)
            if k % 25 == 0: print(f"渲染 {(k + 1) / len(chunks) * 100:.0f}%  {time.time() - t_s:.0f}s", flush=True)
    ff.stdin.close(); ff.wait()
    mix = os.path.join(OUT, "mix.wav")
    if os.path.exists(mix):
        run(["ffmpeg", "-v", "error", "-y", "-i", silent, "-i", mix, "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", dst])
        os.remove(silent)
    else:
        os.replace(silent, dst); print("提示:还没有 out/mix.wav(先运行 hz sfx),这一版没有声音")
    print(f"完成 → {dst}  用时 {time.time() - t_s:.0f}s")

def still(ts):
    import cv2
    for t in ts:
        p = os.path.join(OUT, f"still_{t:.2f}.png"); cv2.imwrite(p, render_frame(SC, int(round(t * FPS)))); print(p)

def board(name, ts, cols=3):
    import cv2, numpy as np
    tw = 640 if W >= H else 300; th = int(tw * H / W); ims = []
    for t in ts:
        f = cv2.resize(render_frame(SC, int(round(t * FPS))), (tw, th), interpolation=cv2.INTER_AREA)
        cv2.rectangle(f, (0, 0), (62, 16), (0, 0, 0), -1); cv2.putText(f, f"{t:.2f}", (3, 12), 0, 0.45, (0, 255, 255), 1); ims.append(f)
    cols = cols if W >= H else 5
    while len(ims) % cols: ims.append(np.zeros_like(ims[0]))
    g = np.vstack([np.hstack(ims[i:i + cols]) for i in range(0, len(ims), cols)]); p = os.path.join(OUT, name + ".jpg"); cv2.imwrite(p, g); print(p)

if __name__ == "__main__":
    args = sys.argv[3:]
    if MODE == "still": still([float(x) for x in args])
    elif MODE == "board": board(args[0], [float(x) for x in args[1:]])
    elif MODE == "preview": video(os.path.join(OUT, "preview.mp4"))
    elif MODE == "final": video(os.path.join(OUT, os.path.basename(EP) + ".mp4"))
    else: raise SystemExit(__doc__)
