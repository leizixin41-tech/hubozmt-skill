"""读入口播(音频或视频)→ work/ 下的统一素材,给剪辑师用。

用法: hz ingest <本期> <口播文件> [--hint "专有名词,逗号分隔"] [--lang zh]

产出(都在 <本期>/work/):
  voice.wav        人声(44.1kHz 立体声,响度统一到 -16 LUFS)
  words.json       逐词时间轴 [{"w":词,"s":起,"e":止}]
  transcript.md    给人和模型读的逐句稿(带时间)+ 停顿列表
  pauses.json      静音停顿 [[起,止],...]
  video.mp4        (视频输入时)统一成恒定帧率的画面,和 voice.wav 等长
  person.json      (视频输入时)每 0.5 秒是否检测到人脸,以及合并后的「有人」时段
  video_sheet.jpg  (视频输入时)每隔几秒一帧的联系表,带时间
  ingest.json      汇总:时长、是否有画面、尺寸、帧率
"""
import os, sys, json, shutil, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *
import numpy as np

ap = argparse.ArgumentParser(); ap.add_argument("ep"); ap.add_argument("src"); ap.add_argument("--hint", default=""); ap.add_argument("--lang", default="zh")
ap.add_argument("--model", default="medium")
a = ap.parse_args()
ep = ep_path(a.ep); W_ = os.path.join(ep, "work"); os.makedirs(W_, exist_ok=True); os.makedirs(os.path.join(ep, "input"), exist_ok=True)
src = os.path.abspath(a.src)
dst = os.path.join(ep, "input", os.path.basename(src))
if not os.path.exists(dst): shutil.copy2(src, dst)

info = probe(dst); streams = info["streams"]
vs = [s for s in streams if s["codec_type"] == "video" and s.get("width")]
has_video = bool(vs) and os.path.splitext(dst)[1].lower() not in (".mp3", ".wav", ".m4a", ".aac", ".flac")
dur = float(info["format"]["duration"])

# ---------- 人声
voice = os.path.join(W_, "voice.wav")
run(["ffmpeg", "-v", "error", "-y", "-i", dst, "-vn", "-af", "loudnorm=I=-16:TP=-1.5:LRA=9", "-ar", "44100", "-ac", "2", voice])
raw = subprocess.run(["ffmpeg", "-v", "error", "-i", voice, "-f", "f32le", "-ac", "1", "-ar", "16000", "-"], capture_output=True).stdout
pcm = np.frombuffer(raw, np.float32)

# ---------- 逐词时间轴
from faster_whisper import WhisperModel
print("语音识别中(本地 faster-whisper,首次运行会下载模型)…", flush=True)
m = WhisperModel(a.model, device="cpu", compute_type="int8")
segs, _ = m.transcribe(pcm, language=a.lang, word_timestamps=True, initial_prompt=(a.hint or None), vad_filter=False)
words, sents = [], []
for s in segs:
    sents.append(dict(s=round(s.start, 2), e=round(s.end, 2), text=s.text.strip()))
    for w in s.words: words.append(dict(w=w.word, s=round(w.start, 2), e=round(w.end, 2)))
json.dump(words, open(os.path.join(W_, "words.json"), "w"), ensure_ascii=False, indent=0)
json.dump(sents, open(os.path.join(W_, "sentences.json"), "w"), ensure_ascii=False, indent=0)
# 停顿:用音量检测静音段(比语音识别的词边界准)
sd = subprocess.run(["ffmpeg", "-v", "info", "-i", voice, "-af", "silencedetect=noise=-38dB:d=0.25", "-f", "null", "-"], capture_output=True, text=True).stderr
import re
st = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", sd)]; en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", sd)]
pauses = [(round(x, 2), round(y, 2)) for x, y in zip(st, en) if x > 0.05 and y < dur - 0.05]
json.dump(pauses, open(os.path.join(W_, "pauses.json"), "w"))

# ---------- 画面
person, vinfo = None, None
if has_video:
    v0 = vs[0]; num, den = (int(x) for x in v0.get("avg_frame_rate", "30/1").split("/")); fps = round(num / max(den, 1)) or 30
    fps = min(60, max(24, fps))
    vid = os.path.join(W_, "video.mp4")
    run(["ffmpeg", "-v", "error", "-y", "-i", dst, "-an", "-vf", f"fps={fps},format=yuv420p", "-c:v", "libx264", "-crf", "16", "-preset", "fast", vid])
    import cv2
    cap = cv2.VideoCapture(vid); W0 = int(cap.get(3)); H0 = int(cap.get(4))
    cv2.setLogLevel(0) if hasattr(cv2, "setLogLevel") else None
    sw = 480; sh = int(sw * H0 / W0)
    det = cv2.FaceDetectorYN.create(os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "face_detection_yunet_2023mar.onnx"), "", (sw, sh), 0.75)
    flags, thumbs, t = [], [], 0.0
    sheet_step = max(2.0, dur / 30)
    next_thumb = 0.0
    while t < dur:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000); ok, fr = cap.read()
        if not ok: break
        _, faces = det.detect(cv2.resize(fr, (sw, sh)))
        nf = 0 if faces is None else int(len(faces))
        big = 0.0 if faces is None else float(max(f[2] * f[3] for f in faces) / (sw * sh))
        flags.append(dict(t=round(t, 2), face=nf > 0, n=nf, area=round(big, 4)))
        if t >= next_thumb:
            th = cv2.resize(fr, (320, int(320 * H0 / W0))); cv2.rectangle(th, (0, 0), (64, 18), (0, 0, 0), -1)
            cv2.putText(th, f"{t:.1f}s", (3, 14), 0, 0.45, (0, 255, 255), 1); thumbs.append(th); next_thumb += sheet_step
        t += 0.5
    # 合并「有人」时段(容忍 1 秒内的漏检)
    spans = []
    for f in flags:
        if f["face"]:
            if spans and f["t"] - spans[-1][1] <= 1.0: spans[-1][1] = f["t"] + 0.5
            else: spans.append([f["t"], f["t"] + 0.5])
    person = dict(samples=flags, spans=[[round(x, 2), round(min(y, dur), 2)] for x, y in spans])
    json.dump(person, open(os.path.join(W_, "person.json"), "w"), ensure_ascii=False)
    if thumbs:
        cols = 6; rows = [thumbs[i:i + cols] for i in range(0, len(thumbs), cols)]
        rows[-1] += [np.zeros_like(thumbs[0])] * (cols - len(rows[-1]))
        cv2.imwrite(os.path.join(W_, "video_sheet.jpg"), np.vstack([np.hstack(r) for r in rows]))
    vinfo = dict(width=W0, height=H0, fps=fps)

# ---------- 汇总 + 逐句稿
summ = dict(source=os.path.basename(dst), duration=round(dur, 2), has_video=has_video, video=vinfo, words=len(words))
json.dump(summ, open(os.path.join(W_, "ingest.json"), "w"), ensure_ascii=False, indent=1)
L = [f"# 口播逐句稿({summ['source']},{dur:.1f} 秒)", "", "语音识别可能有错字,专有名词以口播原意为准。", ""]
for s in sents: L.append(f"- `{s['s']:6.2f}–{s['e']:6.2f}` {s['text']}")
L += ["", f"## 静音停顿(≥0.25 秒,共 {len(pauses)} 处)——剪气口的候选", ""]
L += [f"- {x:.2f} → {y:.2f}(停 {y - x:.2f} 秒)" for x, y in pauses] or ["- 无"]
if person:
    L += ["", "## 画面里有人(人脸检测,仅供参考)", ""]
    L += [f"- {x:.1f} – {y:.1f} 秒" for x, y in person["spans"]] or ["- 没有检测到人脸"]
    L += ["", "画面联系表:`work/video_sheet.jpg`"]
open(os.path.join(W_, "transcript.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
print(json.dumps(summ, ensure_ascii=False))
print("逐句稿 →", os.path.join(W_, "transcript.md"))
