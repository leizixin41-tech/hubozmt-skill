"""出片前后的自动检查(审片用),只查硬伤,不评审美。

用法:
  hz check <本期>                  只查场景脚本:文字是否被挡、是否超出画面、相邻段落是否压盖、每段是否展示完整
  hz check <本期> <视频文件>        再查成片:尺寸/帧率是否与 brief 一致、时长是否覆盖人声、响度;并出抽帧联系表
产出: out/check.json、out/contact.jpg(联系表,带时间;审片必须亲自看这张图)
网页版:本期只有 03_scene.html(没有 03_scenes.py)时,自动改用无界面浏览器每 0.1 秒定格一次检查 .hz-txt 文字
  (完整出现时刻取 data-t0;页面里没有 .hz-txt 时退回「所有有直接文字的元素」):出画/贴边(30px 安全边距)、
  完整出现后 0.5 秒内被更上层元素挡住、两段文字重叠、完整出现到消失/虚化不足 0.6 秒。--workers N 设并行浏览器数(默认 4)。
  --from 秒 --to 秒  只查这一段(改了某一段之后复查用;交给渲染前必须再跑一次全片)。
规范 v2(brief.json 里 "spec": 2)另外查:
  段表门禁(同 hz plan);案例段里「看得清的 UI/截图占画面 ≥18%」的帧 ≥70%、连续只有字 ≤1.5 秒;
  案例段在成片里真的做了段表要求的交互动画数(读 hz_kit.js 的 hz.k.log)。阈值在 tools/plan.py 的 RULE。
"""
import os, sys, json, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *

A = sys.argv[1:]; WORKERS = 4; RNG = [None, None]
if "--workers" in A: i = A.index("--workers"); WORKERS = int(A[i + 1]); del A[i:i + 2]
for j, k in enumerate(("--from", "--to")):
    if k in A: i = A.index(k); RNG[j] = float(A[i + 1]); del A[i:i + 2]
RNG = None if RNG == [None, None] else (RNG[0] or 0.0, RNG[1] if RNG[1] is not None else 1e9)
EP = ep_path(A[0]); VID = A[1] if len(A) > 1 else None
B = setup_engine_env(EP, preview=True)
from plan import spec2, gate, segments_for_check, RULE, KINDS
SP2 = spec2(EP); PLAN = []
if SP2:
    PLAN, _ = gate(EP)
    print("段表门禁:" + ("✅ 通过" if not PLAN else f"❌ {len(PLAN)} 处问题(详情见下,或跑 hz plan)"), flush=True)
WEB = not os.path.exists(os.path.join(EP, "03_scenes.py")) and os.path.exists(os.path.join(EP, "03_scene.html"))
if WEB:
    from _webcheck import check_web
    W_, H_ = (int(x) for x in B["size"].lower().split("x"))
    print(f"网页版版面检查:{WORKERS} 个浏览器并行,每 0.1 秒定格一次…", flush=True)
    lay, det, st = check_web(EP, "03_scene.html", W_, H_, WORKERS, RNG)
    ui_series, klog = st.pop("ui"), st.pop("klog")
    report = dict(layout=lay, layout_detail=det, web=st, video=[], plan=PLAN, rich=[], rich_detail=[], ok=True)
    if RNG: print(f"  只查 {RNG[0]:.2f}–{min(RNG[1], st['dur']):.2f} 秒(交给渲染前要再跑一次全片)")
    if SP2:
        from _webcheck import STEP
        if klog is None: report["rich"].append("页面没有加载 hz_kit.js,核对不了交互动画(规范 v2 的期必须加载)")
        for sid, t0, t1, kind, need in segments_for_check(EP):
            if kind != "case" or (RNG and (t1 < RNG[0] or t0 > RNG[1])): continue
            S = [u for t, u in ui_series if t0 <= t < t1]
            if not S: continue
            good = [u >= RULE["ui_area"] for u in S]; cover = sum(good) / len(good)
            run = best = 0
            for g in good: run = 0 if g else run + 1; best = max(best, run)
            n = sum(1 for k in (klog or []) if k["kind"] in KINDS and t0 - 0.2 <= k["t"] <= t1)
            report["rich_detail"].append(dict(seg=sid, t0=t0, t1=t1, ui_cover=round(cover, 3), ui_mean=round(sum(S) / len(S), 3), text_only_run=round(best * STEP, 1), interactions=n, need=need))
            if cover < RULE["ui_cover"]: report["rich"].append(f"段 {sid}({t0:.2f}–{t1:.2f}):看得清的 UI/截图只在 {cover:.0%} 的时间里占到画面 {RULE['ui_area']:.0%} 以上(要 ≥{RULE['ui_cover']:.0%})")
            if best * STEP > RULE["pure_run"] + 1e-6: report["rich"].append(f"段 {sid}:连续 {best * STEP:.1f} 秒画面上只有字(最长 {RULE['pure_run']} 秒)")
            if klog is not None and n < need: report["rich"].append(f"段 {sid}:成片里只做了 {n} 个交互动画(至少 {need} 个)")
    print(f"  片长 {st['dur']:.1f}s · 定格 {st['samples']} 次 · 识别文字 {st['texts']} 段"
          + (" · 页面没有 .hz-txt,已退回「所有有直接文字的元素」" if st["fallback"] else "") + f" · 用时 {st['seconds']}s")
    node_ts = st["appear"]
else:
    import kit                                  # noqa: E402
    M = load_scenes(EP)
    report = dict(layout=kit.check_layout(verbose=False), video=[], ok=True)
    node_ts = [n.t_in for n in M.scene_nodes]

if VID:
    VID = os.path.abspath(VID); info = probe(VID)
    v = [s for s in info["streams"] if s["codec_type"] == "video"][0]; a = [s for s in info["streams"] if s["codec_type"] == "audio"]
    want_w, want_h = (int(x) for x in B["size"].lower().split("x"))
    if (v["width"], v["height"]) != (want_w, want_h): report["video"].append(f"尺寸 {v['width']}x{v['height']},brief 要求 {B['size']}")
    num, den = (int(x) for x in v["r_frame_rate"].split("/")); fps = num / den
    if abs(fps - float(B["fps"])) > 0.5 and "preview" not in os.path.basename(VID): report["video"].append(f"帧率 {fps:.2f},brief 要求 {B['fps']}")
    dur = float(info["format"]["duration"])
    vd = float(probe(voice_file(EP))["format"]["duration"])
    if dur < vd - 0.05: report["video"].append(f"成片 {dur:.2f}s 比人声 {vd:.2f}s 短,口播被截断")
    if not a: report["video"].append("成片没有音轨")
    else:
        e = subprocess.run(["ffmpeg", "-i", VID, "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
        I = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", e)[-1]); P = float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", e)[-1])
        report["loudness"] = dict(I=I, peak=P)
        if not (-19 <= I <= -13): report["video"].append(f"响度 {I} LUFS,应在 -19 ~ -13 之间")
        if P > -0.5: report["video"].append(f"峰值 {P} dBFS,有削波风险")
    report["duration"] = round(dur, 2)
    # 联系表:按节点到位后 0.8 秒、以及中间均匀取样
    import cv2, numpy as np
    ts = sorted(set([round(min(dur - 0.1, n + 0.8), 2) for n in node_ts] + [round(x, 2) for x in np.linspace(0.3, dur - 0.3, 12)]))
    cap = cv2.VideoCapture(VID); ims = []
    tw = 480 if v["width"] >= v["height"] else 240; th = int(tw * v["height"] / v["width"])
    for t in ts:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000); ok, f = cap.read()
        if not ok: continue
        f = cv2.resize(f, (tw, th), interpolation=cv2.INTER_AREA); cv2.rectangle(f, (0, 0), (60, 16), (0, 0, 0), -1); cv2.putText(f, f"{t:.2f}", (3, 12), 0, 0.42, (0, 255, 255), 1); ims.append(f)
    cols = 4 if v["width"] >= v["height"] else 6
    while len(ims) % cols: ims.append(np.zeros_like(ims[0]))
    cv2.imwrite(os.path.join(EP, "out", "contact.jpg"), np.vstack([np.hstack(ims[i:i + cols]) for i in range(0, len(ims), cols)]))
    report["contact"] = os.path.join(EP, "out", "contact.jpg")

report["ok"] = not report["layout"] and not report["video"] and not report.get("plan") and not report.get("rich")
report["full"] = not RNG
os.makedirs(os.path.join(EP, "out"), exist_ok=True)
json.dump(report, open(os.path.join(EP, "out", "check.json"), "w"), ensure_ascii=False, indent=1)
print("✅ 自动检查通过" if report["ok"] else "❌ 有问题:")
if WEB and report["layout"]:
    from collections import Counter
    print("  版面:" + "、".join(f"{k} {v} 处" for k, v in Counter(d["type"] for d in report["layout_detail"]).items()))
for x in report["layout"] + report["video"] + report.get("plan", []) + report.get("rich", []): print("  -", x)
if report.get("rich_detail"):
    print("  案例段画面构成:" + " · ".join(f"段{d['seg']} UI {d['ui_cover']:.0%} 交互 {d['interactions']}/{d['need']}" for d in report["rich_detail"]))
if VID: print("响度", report.get("loudness"), " 联系表 →", report.get("contact"), "(请亲自看图)")
