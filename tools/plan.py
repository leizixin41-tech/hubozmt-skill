"""策划交接门禁:检查 02_段表.json,不通过就不许进渲染。只管 brief.json 里写了 "spec": 2 的期,旧集不受影响。

用法: hz plan <本期>              查段表
      hz plan <本期> --sfx [--force]  按段表生成音效表 03_sfx.json:每次镜头起飞一声 whoosh,每个交互按它写的 sfx 落在它的时刻
                                    (keytap 自动连敲 8 下,可在交互里写 taps 改次数);已有 03_sfx.json 时要加 --force 才覆盖
查什么(阈值在下面的 RULE,说明见 规范/01_策划检查清单.md):
  - 口播全覆盖:段落首尾相接盖住整条人声,每个词都落在某一段里;每段写了 vo(口播原文)和 logic(展示什么逻辑)
  - 字段齐全:id t0 t1 kind vo logic ui_shot assets interactions text_role depth_plan,缺一不可
  - 案例段(kind=case):主视觉写清楚;至少 1 张真实截图/录屏帧(文件在 assets/,有来源);交互次数够、种类在动画库存里、
    时刻落在段内、写了音效;框选目标「文件#区域名」在截图同名 .json 的 boxes 里
  - 文字只作标注:案例段主标题 ≤1 条、文字 ≤4 条、每条 ≤16 字;每条文字写明挂在哪一层
  - 景深:每段至少用到两层(front/mid/back),focus 写明焦点在哪层
  - 纯文字段(没有素材也没有交互的段)≤3 秒;案例段总时长 ≥ 人声的 50%;全片真实截图 ≥ min(3, 案例段数) 张
  - 不靠生图:生图(role=gen)不能当案例段的唯一素材;brief 的 gen_limit 为 0 时不许出现生图
产出 out/plan_check.json;有问题时列出来并退出码 1。hz check 和 hz web_render final 会自动先跑它。
"""
import os, sys, json, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *

RULE = dict(
    case_min_inter=1, case_long=3.5, case_long_inter=2,   # 案例段交互次数:≥1;超过 3.5 秒的段 ≥2
    text_max_items=4, text_max_title=1, text_max_chars=16,
    pure_text_max=3.0,                                    # 纯文字段最长秒数
    case_share=0.5,                                       # 案例段总时长 / 人声时长
    min_shots=3,                                          # 全片不同的真实截图张数下限(案例段少于 3 段时 = 案例段数)
    gap=0.15,                                             # 相邻两段之间允许的空隙(秒)
    # 以下给 hz check 量成片画面用
    ui_area=0.18,                                         # 一帧里可见 UI/截图占画面 ≥18% 才算「有画面」
    ui_cover=0.7,                                         # 案例段里「有画面」的帧 ≥70%
    pure_run=1.5,                                         # 案例段里连续「只有字」最长 1.5 秒
)
KINDS = ["frame", "pulse", "count", "terminal", "load", "swap", "pills", "click", "code", "hl", "list", "results", "progress", "input"]
SEG_KINDS = ["hook", "case", "bridge", "end"]
SHOT_ROLES = {"screenshot", "crop", "record"}
ASSET_ROLES = SHOT_ROLES | {"logo", "copy", "icon", "gen"}
SFX = {"whoosh", "thump", "tick", "keytap", "pop", "chime", "shimmer", "swish", "none"}
LAYERS = ["front", "mid", "back"]
FIELDS = ["id", "t0", "t1", "kind", "vo", "logic", "ui_shot", "assets", "interactions", "text_role", "depth_plan"]


def spec2(ep):
    return int(brief(ep).get("spec", 1)) >= 2


def load_segments(ep):
    p = os.path.join(ep, "02_段表.json")
    if not os.path.exists(p): return None
    return json.load(open(p, encoding="utf-8"))


def _words(ep):
    for n in ("words_cut.json", "words.json"):
        p = os.path.join(ep, "work", n)
        if os.path.exists(p): return json.load(open(p, encoding="utf-8"))
    return []


def _sidecar(ep, f):
    p = os.path.join(ep, "assets", os.path.splitext(f)[0] + ".json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def gate(ep):
    """返回 (问题列表, 统计)。问题为空 = 通过。"""
    B = brief(ep); P = []
    D = load_segments(ep)
    if D is None: return ["缺 02_段表.json(格式见 规范/模板_02_段表.json)"], {}
    segs = D.get("segments") if isinstance(D, dict) else None
    if not segs: return ["02_段表.json 里没有 segments"], {}
    W = _words(ep)
    if not W: P.append("没有 work/words.json,先跑 hz ingest")
    v0, v1 = (W[0]["s"], W[-1]["e"]) if W else (0, 0)

    # ---- 逐段 ----
    shots, case_dur, n_case = set(), 0.0, 0
    for i, s in enumerate(segs):
        sid = f"段 {s.get('id', i + 1)}"
        miss = [k for k in FIELDS if k not in s]
        if miss: P.append(f"{sid}:缺字段 {'、'.join(miss)}"); continue
        t0, t1, kind = float(s["t0"]), float(s["t1"]), s["kind"]
        if t1 <= t0: P.append(f"{sid}:t1 {t1} 不大于 t0 {t0}")
        if kind not in SEG_KINDS: P.append(f"{sid}:kind「{kind}」不认识,只能是 {'/'.join(SEG_KINDS)}")
        if not str(s["vo"]).strip(): P.append(f"{sid}:vo(口播原文)是空的")
        if not str(s["logic"]).strip(): P.append(f"{sid}:logic(这段展示什么逻辑)是空的")
        A, I, X, Dp = s["assets"], s["interactions"], s["text_role"], s["depth_plan"]
        # 素材
        real = []
        for a in A:
            f, role = a.get("file"), a.get("role")
            if role not in ASSET_ROLES: P.append(f"{sid}:素材 {f or a.get('text', '')[:12]} 的 role「{role}」不认识"); continue
            if role == "gen" and int(B.get("gen_limit", 0)) == 0: P.append(f"{sid}:本期不许生图(gen_limit=0),却用了 {f}")
            if role == "copy":
                if not a.get("text") or not a.get("source"): P.append(f"{sid}:文案素材要写 text 和 source(出处)")
                continue
            if not f or not os.path.exists(os.path.join(ep, "assets", f)): P.append(f"{sid}:素材文件 assets/{f} 不存在"); continue
            sc = _sidecar(ep, f)
            if not (a.get("source") or (sc and sc.get("source"))): P.append(f"{sid}:素材 {f} 没有来源(用 hz capture 截会自动生成同名 .json;否则在段表里写 source)")
            if role in SHOT_ROLES: real.append(f); shots.add(f)
        # 交互
        for x in I:
            k, at = x.get("kind"), x.get("at")
            if k not in KINDS: P.append(f"{sid}:交互「{k}」不在动画库存里({'/'.join(KINDS)})"); continue
            if at is None or not (t0 - 0.2 <= float(at) <= t1): P.append(f"{sid}:交互 {k} 的时刻 {at} 不在本段 {t0}–{t1} 里")
            if x.get("sfx") not in SFX: P.append(f"{sid}:交互 {k}@{at} 的音效 sfx「{x.get('sfx')}」不认识(写 none 表示不配)")
            tg = x.get("target", "")
            if "#" in tg:
                f, bx = tg.split("#", 1); sc = _sidecar(ep, f)
                if not sc or bx not in (sc.get("boxes") or {}): P.append(f"{sid}:交互目标 {tg} 找不到(先用 hz capture --box {bx}=… 量出位置)")
            elif not tg: P.append(f"{sid}:交互 {k}@{at} 没写 target(作用在哪个元素)")
        # 文字
        titles = [x for x in X if x.get("role") == "title"]
        for x in X:
            if x.get("layer") not in LAYERS: P.append(f"{sid}:文字「{x.get('text', '')}」没写挂在哪一层(front/mid/back)")
            if x.get("role") not in ("title", "sub", "label", "note"): P.append(f"{sid}:文字「{x.get('text', '')}」的 role 只能是 title/sub/label/note")
        # 景深
        used = [k for k in LAYERS if Dp.get(k)]
        if len(used) < 2: P.append(f"{sid}:景深只用了 {len(used)} 层,至少两层(front/mid/back),禁止全体同一 z")
        if Dp.get("focus") not in LAYERS: P.append(f"{sid}:depth_plan.focus 要写焦点在哪层(front/mid/back)")
        # 按段类型
        dur = t1 - t0
        if kind == "case":
            n_case += 1; case_dur += dur
            if not str(s["ui_shot"]).strip(): P.append(f"{sid}:案例段没写主视觉 ui_shot")
            if not real: P.append(f"{sid}:案例段没有真实截图/录屏帧(role=screenshot/crop/record)")
            need = RULE["case_long_inter"] if dur > RULE["case_long"] else RULE["case_min_inter"]
            if len(I) < need: P.append(f"{sid}:案例段 {dur:.1f} 秒只有 {len(I)} 个交互动画,至少 {need} 个")
            if len(titles) > RULE["text_max_title"]: P.append(f"{sid}:案例段主标题 {len(titles)} 条,最多 {RULE['text_max_title']} 条(文字只作标注)")
            if len(X) > RULE["text_max_items"]: P.append(f"{sid}:案例段文字 {len(X)} 条,最多 {RULE['text_max_items']} 条")
            for x in X:
                if len(str(x.get("text", ""))) > RULE["text_max_chars"]: P.append(f"{sid}:文字「{x['text']}」超过 {RULE['text_max_chars']} 字,拆短或交给画面")
        elif not real and not I and dur > RULE["pure_text_max"] + 1e-6:
            P.append(f"{sid}:纯文字段 {dur:.1f} 秒,最长 {RULE['pure_text_max']} 秒(拆段,或加截图/交互)")

    # ---- 全片 ----
    ok = [s for s in segs if all(k in s for k in ("t0", "t1"))]
    ok.sort(key=lambda s: float(s["t0"]))
    for a, b in zip(ok, ok[1:]):
        g = float(b["t0"]) - float(a["t1"])
        if g > RULE["gap"]: P.append(f"段 {a.get('id')}→{b.get('id')}:中间空了 {g:.2f} 秒没有画面设计")
        if g < -0.01: P.append(f"段 {a.get('id')}→{b.get('id')}:时间重叠 {-g:.2f} 秒")
    if W and ok:
        if float(ok[0]["t0"]) > v0 + 0.05: P.append(f"第一段从 {ok[0]['t0']} 开始,口播 {v0:.2f} 就开口了")
        if float(ok[-1]["t1"]) < v1 - 0.05: P.append(f"最后一段到 {ok[-1]['t1']} 结束,口播到 {v1:.2f} 才说完")
        lost = [w for w in W if not any(float(s["t0"]) - 0.05 <= (w["s"] + w["e"]) / 2 <= float(s["t1"]) + 0.05 for s in ok)]
        if lost: P.append("这些词没有映射到任何一段:" + "、".join(f"「{w['w']}」@{w['s']:.2f}" for w in lost[:12]) + (" …" if len(lost) > 12 else ""))
    total = max(1e-6, v1 - v0)
    if W and case_dur / total < RULE["case_share"]: P.append(f"案例段总共 {case_dur:.1f} 秒,只占人声 {case_dur / total:.0%},至少 {RULE['case_share']:.0%}")
    need = min(RULE["min_shots"], n_case)
    if len(shots) < need: P.append(f"全片真实截图只有 {len(shots)} 张,至少 {need} 张")
    st = dict(segments=len(segs), case=n_case, case_share=round(case_dur / total, 3) if W else None, shots=sorted(shots))
    return P, st


def segments_for_check(ep):
    """给 hz check 用:[(id, t0, t1, kind, 至少几个交互)]。"""
    D = load_segments(ep) or {}
    out = []
    for s in D.get("segments", []):
        try:
            t0, t1 = float(s["t0"]), float(s["t1"])
            need = RULE["case_long_inter"] if t1 - t0 > RULE["case_long"] else RULE["case_min_inter"]
            out.append((s.get("id"), t0, t1, s.get("kind"), need))
        except Exception: pass
    return out


SFX_VOL = dict(whoosh=0.3, thump=0.45, tick=0.38, keytap=0.2, pop=0.38, chime=0.32, shimmer=0.28, swish=0.3)


def sfx_from_plan(ep):
    """段表 → 03_sfx.json 的内容:音效挂钩点 = 镜头起飞(段起点前 0.05 秒)+ 每个交互的时刻。"""
    segs = sorted(load_segments(ep)["segments"], key=lambda s: float(s["t0"]))
    ev = []
    for i, s in enumerate(segs):
        if i: ev.append([round(float(s["t0"]) - 0.05, 3), "whoosh", SFX_VOL["whoosh"], {"dur": 0.55}])
        for x in s.get("interactions", []):
            k, at = x.get("sfx"), float(x["at"])
            if k in (None, "none") or k not in SFX_VOL: continue
            if k == "keytap": ev += [[round(at + j * 0.085, 3), "keytap", SFX_VOL[k], {"depth": 0.8 + 0.3 * (j % 3) / 2}] for j in range(int(x.get("taps", 8)))]
            else: ev.append([round(at, 3), k, SFX_VOL[k]])
    return dict(dur=max(float(s["t1"]) for s in segs), sfx=sorted(ev, key=lambda e: e[0]))


def main():
    ep = ep_path(sys.argv[1])
    if "--sfx" in sys.argv:
        p = os.path.join(ep, "03_sfx.json")
        if os.path.exists(p) and "--force" not in sys.argv: raise SystemExit("已有 03_sfx.json;要覆盖就加 --force")
        D = sfx_from_plan(ep); json.dump(D, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        print(f"✅ 03_sfx.json:{len(D['sfx'])} 个音效,时长 {D['dur']} 秒(合成师可再微调)"); return
    if not spec2(ep): print("ℹ️ 本期 brief.json 没写 \"spec\": 2,按旧规范出片,不查段表。")
    P, st = gate(ep)
    os.makedirs(os.path.join(ep, "out"), exist_ok=True)
    json.dump(dict(ok=not P, problems=P, stat=st, rule=RULE), open(os.path.join(ep, "out", "plan_check.json"), "w"), ensure_ascii=False, indent=1)
    if st: print(f"段表:{st['segments']} 段,案例段 {st['case']} 段(占人声 {st['case_share'] or 0:.0%}),真实截图 {len(st['shots'])} 张")
    if P:
        print(f"❌ 段表不合格({len(P)} 处),改好再交给合成师:"); [print("  -", x) for x in P]; sys.exit(1)
    print("✅ 段表合格,可以交给合成师")


if __name__ == "__main__":
    main()
