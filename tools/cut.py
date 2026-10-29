"""按剪辑师的决定剪掉气口/口误:人声和真人画面同步剪,时间轴同步改。

用法: hz cut <本期>
读取 <本期>/work/cuts.json(剪辑师写):
  {"remove": [[起, 止], ...]}      要删掉的时间段(秒,以原始口播为准)
产出(work/):
  voice_cut.wav  video_cut.mp4(有画面时)  words_cut.json  timemap.json(原时间 → 新时间)
  transcript_cut.md                        剪后的逐句稿
之后所有工具自动优先使用剪过的版本。不需要剪时不要写 cuts.json(或写空列表)。
"""
import os, sys, json, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *

ap = argparse.ArgumentParser(); ap.add_argument("ep"); a = ap.parse_args()
ep = ep_path(a.ep); W_ = os.path.join(ep, "work")
ing = json.load(open(os.path.join(W_, "ingest.json"))); dur = ing["duration"]
rm = sorted(json.load(open(os.path.join(W_, "cuts.json"))).get("remove", []))
keep, cur = [], 0.0
for s, e in rm:
    s, e = max(0.0, s), min(dur, e)
    if s > cur + 0.02: keep.append([cur, s])
    cur = max(cur, e)
if cur < dur - 0.02: keep.append([cur, dur])
if not rm: keep = [[0.0, dur]]

# 时间映射:原时间 t → 新时间
offs, acc = [], 0.0
for s, e in keep: offs.append((s, e, acc)); acc += e - s
def remap(t):
    for s, e, o in offs:
        if t < s: return o
        if t <= e: return o + (t - s)
    return acc
json.dump(dict(keep=keep, new_duration=round(acc, 3)), open(os.path.join(W_, "timemap.json"), "w"), indent=1)

FADE = 0.012          # 每个剪辑点 12ms 淡入淡出,避免爆音
def build(kind):
    parts, labels = [], []
    for i, (s, e) in enumerate(keep):
        if kind == "a":
            parts.append(f"[0:a]atrim={s:.3f}:{e:.3f},asetpts=PTS-STARTPTS,afade=t=in:d={FADE},afade=t=out:st={max(0, e - s - FADE):.3f}:d={FADE}[a{i}]"); labels.append(f"[a{i}]")
        else:
            parts.append(f"[0:v]trim={s:.3f}:{e:.3f},setpts=PTS-STARTPTS[v{i}]"); labels.append(f"[v{i}]")
    n = len(keep)
    parts.append("".join(labels) + (f"concat=n={n}:v=0:a=1[o]" if kind == "a" else f"concat=n={n}:v=1:a=0[o]"))
    return ";".join(parts)

run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(W_, "voice.wav"), "-filter_complex", build("a"), "-map", "[o]", "-ar", "44100", "-ac", "2", os.path.join(W_, "voice_cut.wav")])
if ing.get("has_video"):
    run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(W_, "video.mp4"), "-filter_complex", build("v"), "-map", "[o]", "-c:v", "libx264", "-crf", "16", "-preset", "fast", "-pix_fmt", "yuv420p", os.path.join(W_, "video_cut.mp4")])

words = json.load(open(os.path.join(W_, "words.json"))); out = []
for w in words:
    mid = (w["s"] + w["e"]) / 2
    if any(s <= mid <= e for s, e in rm): continue
    out.append(dict(w=w["w"], s=round(remap(w["s"]), 2), e=round(remap(w["e"]), 2)))
json.dump(out, open(os.path.join(W_, "words_cut.json"), "w"), ensure_ascii=False, indent=0)
# 剪后逐句稿:按原句子边界重组(句内被删的词去掉)
L = [f"# 剪后逐句稿(新时长 {acc:.2f} 秒,删掉 {dur - acc:.2f} 秒)", ""]
for se in json.load(open(os.path.join(W_, "sentences.json"))):
    ws = [w for w in words if se["s"] - 0.01 <= (w["s"] + w["e"]) / 2 <= se["e"] + 0.01 and not any(s <= (w["s"] + w["e"]) / 2 <= e for s, e in rm)]
    if ws: L.append(f"- `{remap(ws[0]['s']):6.2f}–{remap(ws[-1]['e']):6.2f}` {''.join(w['w'] for w in ws).strip()}")
open(os.path.join(W_, "transcript_cut.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
print(f"剪完:{dur:.2f}s → {acc:.2f}s,保留 {len(keep)} 段")
