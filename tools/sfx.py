"""合成音效并与人声混音(不做背景音乐,给你后期加配乐留余量)。

用法: hz sfx <本期>
音效事件写在 03_scenes.py 里:
  SFX = [(时刻, "种类", 音量), (时刻, "种类", 音量, {"pan": 0.3, "dur": 0.5, ...}), ...]
  种类: whoosh(dur,bright) thump(f0,dur,click) tick(f,dur,tone) keytap(depth) pop(f0,f1,dur) chime(f,dur) shimmer(dur,base) swish(dur)
  另外每次镜头飞行会自动加一声呼啸;不想要就在脚本里写 AUTO_WHOOSH = False。
产出(out/):
  stem_voice.wav  人声分轨   stem_sfx.wav  音效分轨   mix.wav  混音(人声 -16 LUFS,音效被人声轻压)
"""
import os, sys, wave
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *
import _sfxlib as X
import numpy as np

EP = ep_path(sys.argv[1])
_J = os.path.join(EP, "03_sfx.json")
if os.path.exists(_J):   # 网页场景:音效写在 03_sfx.json {"dur": 秒, "sfx": [[时刻, 种类, 音量, {参数}], ...]}
    import json, types
    _d = json.load(open(_J)); M = types.SimpleNamespace(DUR=_d["dur"], SFX=_d["sfx"], AUTO_WHOOSH=False, scene_nodes=[])
else:
    setup_engine_env(EP, preview=True); M = load_scenes(EP)
DUR = float(M.DUR); OUT = os.path.join(EP, "out"); os.makedirs(OUT, exist_ok=True)
buf = np.zeros((int(DUR * X.SR) + X.SR, 2), np.float32)
KIND = dict(whoosh=X.whoosh, thump=X.thump, tick=X.tick, keytap=X.keytap, pop=X.pop, chime=X.chime, shimmer=X.shimmer, swish=X.swish)
DEFAULT = dict(whoosh=dict(dur=0.6))

if getattr(M, "AUTO_WHOOSH", True):
    ns = sorted(M.scene_nodes, key=lambda n: n.t_in)
    for n in ns[1:]:
        st = n.t_in - n.flight * n.pre
        if n.flight > 0.05: X.add(buf, st - 0.02, X.whoosh(n.flight * 1.25, 1.25 if n.flight < 0.62 else 0.9), 0.26, pan=0.25)

bad = []
for ev in getattr(M, "SFX", []):
    t, kind, gain = ev[0], ev[1], (ev[2] if len(ev) > 2 else 0.4); kw = dict(DEFAULT.get(kind, {})); kw.update(ev[3] if len(ev) > 3 else {})
    pan = kw.pop("pan", 0.0)
    if kind not in KIND: bad.append(kind); continue
    X.add(buf, t, KIND[kind](**kw), gain, pan=pan)
if bad: print("未知音效种类(已跳过):", sorted(set(bad)))
buf[:] = np.tanh(buf * 0.9)

def wav(path, arr):
    x = (np.clip(arr, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as w: w.setnchannels(2); w.setsampwidth(2); w.setframerate(X.SR); w.writeframes(x.tobytes())
sfx = os.path.join(OUT, "stem_sfx.wav"); wav(sfx, buf[:int(DUR * X.SR)])
voice = os.path.join(OUT, "stem_voice.wav")
run(["ffmpeg", "-v", "error", "-y", "-i", voice_file(EP), "-af", f"apad=whole_dur={DUR}", "-t", str(DUR), "-ar", str(X.SR), "-ac", "2", voice])
run(["ffmpeg", "-v", "error", "-y", "-i", voice, "-i", sfx, "-filter_complex",
     "[0:a]asplit=2[v1][v2];[1:a][v2]sidechaincompress=threshold=0.03:ratio=4:attack=8:release=220[sd];"
     "[v1][sd]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.89[m]", "-map", "[m]", "-t", str(DUR), os.path.join(OUT, "mix.wav")])
print("音效分轨 →", sfx); print("人声分轨 →", voice); print("混音 →", os.path.join(OUT, "mix.wav"))
